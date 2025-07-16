import asyncio
import json
import logging
import websockets
from datetime import datetime
from typing import Dict, List, Set
from fastapi import WebSocket
import os

from models.data_models import WebSocketMessage, RealTimeQuote, DataTier
from services.polygon_service import PolygonDataService

logger = logging.getLogger(__name__)

class WebSocketManager:
    """Manager for WebSocket connections and real-time data streaming"""
    
    def __init__(self, polygon_service: PolygonDataService):
        self.polygon_service = polygon_service
        self.connections: Dict[str, List[WebSocket]] = {}  # symbol -> list of connections
        self.polygon_ws = None
        self.subscribed_symbols: Set[str] = set()
        self.api_key = os.getenv('POLYGON_API_KEY', 'demo_key')
        
    async def connect(self, websocket: WebSocket, symbol: str):
        """Add a new WebSocket connection for a symbol"""
        if symbol not in self.connections:
            self.connections[symbol] = []
        
        self.connections[symbol].append(websocket)
        
        # Subscribe to symbol if not already subscribed
        if symbol not in self.subscribed_symbols:
            await self.subscribe_to_symbol(symbol)
        
        logger.info(f"WebSocket connected for {symbol}, total connections: {len(self.connections[symbol])}")
        
        # Send initial data
        try:
            quote = await self.polygon_service.get_real_time_quote(symbol, DataTier.INSTITUTIONAL_ELITE)
            message = WebSocketMessage(
                type='quote',
                symbol=symbol,
                data=quote.to_dict(),
                timestamp=datetime.now()
            )
            await websocket.send_text(message.to_json())
        except Exception as e:
            logger.error(f"Error sending initial data for {symbol}: {str(e)}")
    
    async def disconnect(self, websocket: WebSocket, symbol: str):
        """Remove a WebSocket connection"""
        if symbol in self.connections:
            try:
                self.connections[symbol].remove(websocket)
                
                # If no more connections for this symbol, unsubscribe
                if not self.connections[symbol]:
                    del self.connections[symbol]
                    await self.unsubscribe_from_symbol(symbol)
                
                logger.info(f"WebSocket disconnected for {symbol}")
            except ValueError:
                # Connection not in list
                pass
    
    async def disconnect_all(self):
        """Disconnect all WebSocket connections"""
        for symbol, connections in self.connections.items():
            for websocket in connections:
                try:
                    await websocket.close()
                except Exception as e:
                    logger.error(f"Error closing WebSocket for {symbol}: {str(e)}")
        
        self.connections.clear()
        self.subscribed_symbols.clear()
        
        if self.polygon_ws:
            await self.polygon_ws.close()
    
    async def broadcast_to_symbol(self, symbol: str, message: WebSocketMessage):
        """Broadcast a message to all connections for a symbol"""
        if symbol not in self.connections:
            return
        
        disconnected = []
        
        for websocket in self.connections[symbol]:
            try:
                await websocket.send_text(message.to_json())
            except Exception as e:
                logger.error(f"Error sending message to WebSocket for {symbol}: {str(e)}")
                disconnected.append(websocket)
        
        # Remove disconnected WebSockets
        for websocket in disconnected:
            try:
                self.connections[symbol].remove(websocket)
            except ValueError:
                pass
    
    async def subscribe_to_symbol(self, symbol: str):
        """Subscribe to real-time data for a symbol"""
        if self.polygon_ws and not self.polygon_ws.closed:
            subscribe_message = {
                "action": "subscribe",
                "params": f"Q.{symbol}"  # Quote data
            }
            
            try:
                await self.polygon_ws.send(json.dumps(subscribe_message))
                self.subscribed_symbols.add(symbol)
                logger.info(f"Subscribed to {symbol}")
            except Exception as e:
                logger.error(f"Error subscribing to {symbol}: {str(e)}")
    
    async def unsubscribe_from_symbol(self, symbol: str):
        """Unsubscribe from real-time data for a symbol"""
        if self.polygon_ws and not self.polygon_ws.closed:
            unsubscribe_message = {
                "action": "unsubscribe",
                "params": f"Q.{symbol}"
            }
            
            try:
                await self.polygon_ws.send(json.dumps(unsubscribe_message))
                self.subscribed_symbols.discard(symbol)
                logger.info(f"Unsubscribed from {symbol}")
            except Exception as e:
                logger.error(f"Error unsubscribing from {symbol}: {str(e)}")
    
    async def start_polygon_websocket(self):
        """Start and maintain connection to Polygon WebSocket"""
        websocket_url = f"wss://socket.polygon.io/stocks"
        
        while True:
            try:
                logger.info("Connecting to Polygon WebSocket...")
                
                async with websockets.connect(websocket_url) as websocket:
                    self.polygon_ws = websocket
                    
                    # Authenticate
                    auth_message = {
                        "action": "auth",
                        "params": self.api_key
                    }
                    await websocket.send(json.dumps(auth_message))
                    
                    # Wait for auth response
                    auth_response = await websocket.recv()
                    auth_data = json.loads(auth_response)
                    
                    if auth_data.get('status') == 'auth_success':
                        logger.info("Polygon WebSocket authenticated successfully")
                        
                        # Resubscribe to symbols
                        for symbol in list(self.subscribed_symbols):
                            await self.subscribe_to_symbol(symbol)
                        
                        # Listen for messages
                        async for message in websocket:
                            await self.handle_polygon_message(message)
                    else:
                        logger.error(f"Polygon WebSocket authentication failed: {auth_data}")
                        await asyncio.sleep(30)
                        continue
                        
            except websockets.exceptions.ConnectionClosed:
                logger.warning("Polygon WebSocket connection closed, reconnecting...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Polygon WebSocket error: {str(e)}")
                await asyncio.sleep(30)
    
    async def handle_polygon_message(self, message: str):
        """Handle incoming message from Polygon WebSocket"""
        try:
            data = json.loads(message)
            
            # Handle different message types
            if isinstance(data, list):
                for item in data:
                    await self.process_polygon_data(item)
            else:
                await self.process_polygon_data(data)
                
        except Exception as e:
            logger.error(f"Error handling Polygon message: {str(e)}")
    
    async def process_polygon_data(self, data: dict):
        """Process individual data item from Polygon"""
        try:
            msg_type = data.get('ev')  # Event type
            symbol = data.get('sym')  # Symbol
            
            if not symbol:
                return
            
            if msg_type == 'Q':  # Quote
                quote = RealTimeQuote(
                    symbol=symbol,
                    bid=data.get('bp', 0.0),
                    ask=data.get('ap', 0.0),
                    bid_size=data.get('bs', 0),
                    ask_size=data.get('as', 0),
                    timestamp=datetime.fromtimestamp(data.get('t', 0) / 1000)
                )
                
                message = WebSocketMessage(
                    type='quote',
                    symbol=symbol,
                    data=quote.to_dict(),
                    timestamp=datetime.now()
                )
                
                await self.broadcast_to_symbol(symbol, message)
                
            elif msg_type == 'T':  # Trade
                trade_data = {
                    'price': data.get('p', 0.0),
                    'size': data.get('s', 0),
                    'timestamp': datetime.fromtimestamp(data.get('t', 0) / 1000).isoformat(),
                    'conditions': data.get('c', []),
                    'exchange': data.get('x', '')
                }
                
                message = WebSocketMessage(
                    type='trade',
                    symbol=symbol,
                    data=trade_data,
                    timestamp=datetime.now()
                )
                
                await self.broadcast_to_symbol(symbol, message)
                
            elif msg_type == 'A':  # Aggregate (minute bar)
                aggregate_data = {
                    'open': data.get('o', 0.0),
                    'high': data.get('h', 0.0),
                    'low': data.get('l', 0.0),
                    'close': data.get('c', 0.0),
                    'volume': data.get('v', 0),
                    'timestamp': datetime.fromtimestamp(data.get('s', 0) / 1000).isoformat()
                }
                
                message = WebSocketMessage(
                    type='aggregate',
                    symbol=symbol,
                    data=aggregate_data,
                    timestamp=datetime.now()
                )
                
                await self.broadcast_to_symbol(symbol, message)
                
        except Exception as e:
            logger.error(f"Error processing Polygon data: {str(e)}")
    
    async def send_heartbeat(self):
        """Send heartbeat to all connections"""
        heartbeat_message = WebSocketMessage(
            type='heartbeat',
            symbol='',
            data={'status': 'alive'},
            timestamp=datetime.now()
        )
        
        for symbol in self.connections:
            await self.broadcast_to_symbol(symbol, heartbeat_message)
    
    def get_connection_stats(self) -> dict:
        """Get statistics about current connections"""
        total_connections = sum(len(connections) for connections in self.connections.values())
        
        return {
            'total_connections': total_connections,
            'subscribed_symbols': len(self.subscribed_symbols),
            'symbols': list(self.subscribed_symbols),
            'polygon_ws_connected': self.polygon_ws and not self.polygon_ws.closed
        }
