class AdminDashboard {
    constructor() {
        this.websocket = null;
        this.priceChart = null;
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.initChart();
        this.loadDashboardData();
        this.startStatusUpdates();
    }

    setupEventListeners() {
        document.getElementById('fetch-data-btn').addEventListener('click', () => this.fetchMarketData());
        document.getElementById('fetch-quote-btn').addEventListener('click', () => this.fetchQuote());
        document.getElementById('warm-cache-btn').addEventListener('click', () => this.warmCache());
        document.getElementById('connect-ws-btn').addEventListener('click', () => this.connectWebSocket());
        document.getElementById('disconnect-ws-btn').addEventListener('click', () => this.disconnectWebSocket());
    }

    initChart() {
        const ctx = document.getElementById('price-chart').getContext('2d');
        this.priceChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Price',
                    data: [],
                    borderColor: 'rgb(75, 192, 192)',
                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: false
                    }
                }
            }
        });
    }

    async loadDashboardData() {
        try {
            // Load health check
            const healthResponse = await fetch('/health');
            const healthData = await healthResponse.json();
            
            document.getElementById('service-status').textContent = healthData.status;
            
            // Load cache stats
            const cacheResponse = await fetch('/api/cache/stats');
            const cacheData = await cacheResponse.json();
            
            document.getElementById('cache-hit-rate').textContent = `${cacheData.hit_rate || 0}%`;
            
            // Update cache stats display
            this.updateCacheStats(cacheData);
            
        } catch (error) {
            console.error('Error loading dashboard data:', error);
            document.getElementById('service-status').textContent = 'Error';
        }
    }

    updateCacheStats(stats) {
        const statsHtml = `
            <div>Memory Used: ${stats.used_memory || 'N/A'}</div>
            <div>Total Keys: ${stats.key_counts?.total || 0}</div>
            <div>Quotes: ${stats.key_counts?.quotes || 0}</div>
            <div>Market Data: ${stats.key_counts?.market_data || 0}</div>
            <div>Commands: ${stats.total_commands_processed || 0}</div>
        `;
        document.getElementById('cache-stats').innerHTML = statsHtml;
    }

    async fetchMarketData() {
        const symbol = document.getElementById('symbol-input').value.toUpperCase();
        const timespan = document.getElementById('timespan-select').value;
        const tier = document.getElementById('tier-select').value;
        
        if (!symbol) {
            alert('Please enter a symbol');
            return;
        }

        try {
            const response = await fetch(`/api/market-data/${symbol}?timespan=${timespan}&limit=100&tier=${tier}`);
            const data = await response.json();
            
            if (response.ok) {
                this.displayResponse(data);
                this.updateChart(data);
            } else {
                this.displayError(data);
            }
        } catch (error) {
            this.displayError({ error: error.message });
        }
    }

    async fetchQuote() {
        const symbol = document.getElementById('symbol-input').value.toUpperCase();
        const tier = document.getElementById('tier-select').value;
        
        if (!symbol) {
            alert('Please enter a symbol');
            return;
        }

        try {
            const response = await fetch(`/api/quote/${symbol}?tier=${tier}`);
            const data = await response.json();
            
            if (response.ok) {
                this.displayResponse(data);
            } else {
                this.displayError(data);
            }
        } catch (error) {
            this.displayError({ error: error.message });
        }
    }

    async warmCache() {
        const symbolsInput = document.getElementById('warm-symbols').value;
        const symbols = symbolsInput.split(',').map(s => s.trim().toUpperCase()).filter(s => s);
        
        if (symbols.length === 0) {
            alert('Please enter at least one symbol');
            return;
        }

        try {
            const response = await fetch('/api/cache/warm', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(symbols)
            });
            
            const data = await response.json();
            this.displayResponse(data);
            
            // Refresh cache stats
            setTimeout(() => this.loadDashboardData(), 2000);
        } catch (error) {
            this.displayError({ error: error.message });
        }
    }

    connectWebSocket() {
        const symbol = document.getElementById('ws-symbol').value.toUpperCase();
        
        if (!symbol) {
            alert('Please enter a symbol');
            return;
        }

        if (this.websocket) {
            this.websocket.close();
        }

        const wsUrl = `ws://${window.location.host}/ws/${symbol}`;
        this.websocket = new WebSocket(wsUrl);

        this.websocket.onopen = () => {
            console.log('WebSocket connected');
            document.getElementById('connect-ws-btn').style.display = 'none';
            document.getElementById('disconnect-ws-btn').style.display = 'inline-block';
            document.getElementById('websocket-connections').textContent = '1';
            this.updateStatus('Connected to WebSocket');
        };

        this.websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleWebSocketMessage(data);
        };

        this.websocket.onclose = () => {
            console.log('WebSocket disconnected');
            document.getElementById('connect-ws-btn').style.display = 'inline-block';
            document.getElementById('disconnect-ws-btn').style.display = 'none';
            document.getElementById('websocket-connections').textContent = '0';
            this.updateStatus('WebSocket disconnected');
        };

        this.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.updateStatus('WebSocket error');
        };
    }

    disconnectWebSocket() {
        if (this.websocket) {
            this.websocket.close();
        }
    }

    handleWebSocketMessage(data) {
        const wsDataDiv = document.getElementById('ws-data');
        
        if (data.type === 'quote') {
            const quote = data.data;
            wsDataDiv.innerHTML = `
                <div><strong>Symbol:</strong> ${quote.symbol}</div>
                <div><strong>Bid:</strong> $${quote.bid}</div>
                <div><strong>Ask:</strong> $${quote.ask}</div>
                <div><strong>Spread:</strong> $${quote.spread}</div>
                <div><strong>Time:</strong> ${new Date(quote.timestamp).toLocaleTimeString()}</div>
            `;
            
            // Update chart with real-time data
            this.addRealtimeDataToChart(quote);
        } else if (data.type === 'trade') {
            const trade = data.data;
            wsDataDiv.innerHTML = `
                <div><strong>Trade Price:</strong> $${trade.price}</div>
                <div><strong>Size:</strong> ${trade.size}</div>
                <div><strong>Time:</strong> ${new Date(trade.timestamp).toLocaleTimeString()}</div>
            `;
        } else if (data.type === 'heartbeat') {
            // Just update the status
            this.updateStatus('WebSocket active');
        }
    }

    addRealtimeDataToChart(quote) {
        const chart = this.priceChart;
        const now = new Date().toLocaleTimeString();
        const midpoint = (quote.bid + quote.ask) / 2;
        
        // Add new data point
        chart.data.labels.push(now);
        chart.data.datasets[0].data.push(midpoint);
        
        // Keep only last 50 points
        if (chart.data.labels.length > 50) {
            chart.data.labels.shift();
            chart.data.datasets[0].data.shift();
        }
        
        chart.update('none');
    }

    updateChart(data) {
        if (!data.data || data.data.length === 0) return;
        
        const chart = this.priceChart;
        
        // Clear existing data
        chart.data.labels = [];
        chart.data.datasets[0].data = [];
        
        // Add new data
        data.data.forEach(item => {
            const date = new Date(item.timestamp);
            chart.data.labels.push(date.toLocaleDateString());
            chart.data.datasets[0].data.push(item.close);
        });
        
        chart.update();
    }

    displayResponse(data) {
        const responseDiv = document.getElementById('api-response');
        responseDiv.textContent = JSON.stringify(data, null, 2);
    }

    displayError(error) {
        const responseDiv = document.getElementById('api-response');
        responseDiv.textContent = JSON.stringify(error, null, 2);
        responseDiv.style.color = '#ff6b6b';
    }

    updateStatus(message) {
        document.getElementById('status').textContent = message;
    }

    startStatusUpdates() {
        setInterval(() => {
            this.loadDashboardData();
        }, 30000); // Update every 30 seconds
    }
}

// Initialize the dashboard when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new AdminDashboard();
});
