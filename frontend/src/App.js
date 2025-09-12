import React, { useState, useEffect } from 'react';
import { Search, Filter, Calendar, ExternalLink, RefreshCw, Heart, BookOpen, Microscope, Pill, Building2, Shield, Clock, Activity, TrendingUp, TrendingDown, DollarSign, BarChart3, ChevronRight } from 'lucide-react';
import './App.css';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const CATEGORY_ICONS = {
  'Academic Research': BookOpen,
  'Industry Updates': Building2,
  'Early Discovery': Microscope,
  'Clinical Trials': Heart,
  'Drug Modalities': Pill,
  'Healthcare & Policy': Shield
};

const CATEGORY_COLORS = {
  'Academic Research': 'from-emerald-500 to-teal-600',
  'Industry Updates': 'from-blue-500 to-indigo-600',
  'Early Discovery': 'from-purple-500 to-violet-600',
  'Clinical Trials': 'from-red-500 to-pink-600',
  'Drug Modalities': 'from-orange-500 to-amber-600',
  'Healthcare & Policy': 'from-green-500 to-emerald-600'
};

function App() {
  const [articles, setArticles] = useState([]);
  const [stocks, setStocks] = useState([]);
  const [categories, setCategories] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [currentTab, setCurrentTab] = useState('news'); // 'news' or 'stocks'
  const [stockView, setStockView] = useState('all'); // 'all', 'gainers', 'losers'
  const [loading, setLoading] = useState(true);
  const [stocksLoading, setStocksLoading] = useState(false);
  const [systemStatus, setSystemStatus] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    fetchCategories();
    fetchArticles();
    fetchSystemStatus();
    if (currentTab === 'stocks') {
      fetchStocks();
    }
  }, [currentTab]);

  const fetchCategories = async () => {
    try {
      const response = await axios.get(`${API}/categories`);
      setCategories(response.data.categories);
    } catch (error) {
      console.error('Error fetching categories:', error);
    }
  };

  const fetchSystemStatus = async () => {
    try {
      const response = await axios.get(`${API}/status`);
      setSystemStatus(response.data);
    } catch (error) {
      console.error('Error fetching system status:', error);
    }
  };

  const fetchArticles = async (category = '') => {
    try {
      setLoading(true);
      const params = category ? { category } : {};
      const response = await axios.get(`${API}/articles`, { params });
      setArticles(response.data);
    } catch (error) {
      console.error('Error fetching articles:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchStocks = async (view = 'all') => {
    try {
      setStocksLoading(true);
      let endpoint = `${API}/stocks`;
      
      if (view === 'gainers') {
        endpoint = `${API}/stocks/gainers`;
      } else if (view === 'losers') {
        endpoint = `${API}/stocks/losers`;
      }
      
      const response = await axios.get(endpoint);
      setStocks(response.data);
    } catch (error) {
      console.error('Error fetching stocks:', error);
    } finally {
      setStocksLoading(false);
    }
  };

  const refreshArticles = async () => {
    try {
      setRefreshing(true);
      const response = await axios.post(`${API}/articles/refresh`);
      
      if (response.data.message) {
        console.log('Refresh result:', response.data.message);
      }
      
      await Promise.all([
        fetchArticles(selectedCategory),
        fetchSystemStatus()
      ]);
      
    } catch (error) {
      console.error('Error refreshing articles:', error);
    } finally {
      setRefreshing(false);
    }
  };

  const refreshStocks = async () => {
    try {
      setRefreshing(true);
      const response = await axios.post(`${API}/stocks/refresh`);
      
      if (response.data.message) {
        console.log('Stock refresh result:', response.data.message);
      }
      
      await Promise.all([
        fetchStocks(stockView),
        fetchSystemStatus()
      ]);
      
    } catch (error) {
      console.error('Error refreshing stocks:', error);
    } finally {
      setRefreshing(false);
    }
  };

  const searchArticles = async () => {
    if (!searchQuery.trim()) {
      fetchArticles(selectedCategory);
      return;
    }

    try {
      setLoading(true);
      const response = await axios.post(`${API}/search`, {
        query: searchQuery,
        category: selectedCategory || null,
        limit: 20
      });
      setArticles(response.data);
    } catch (error) {
      console.error('Error searching articles:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCategoryChange = (category) => {
    setSelectedCategory(category);
    fetchArticles(category);
  };

  const handleStockViewChange = (view) => {
    setStockView(view);
    fetchStocks(view);
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  const getTimeSince = (dateString) => {
    const now = new Date();
    const date = new Date(dateString);
    const diffInHours = Math.floor((now - date) / (1000 * 60 * 60));
    
    if (diffInHours < 1) return 'Less than an hour ago';
    if (diffInHours < 24) return `${diffInHours} hours ago`;
    
    const diffInDays = Math.floor(diffInHours / 24);
    if (diffInDays < 7) return `${diffInDays} days ago`;
    
    return formatDate(dateString);
  };

  const formatPrice = (price) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2
    }).format(price);
  };

  const formatNumber = (num) => {
    if (!num || isNaN(num)) return '0';
    
    if (num >= 1e12) {
      return (num / 1e12).toFixed(1) + 'T';
    } else if (num >= 1e9) {
      return (num / 1e9).toFixed(1) + 'B';
    } else if (num >= 1e6) {
      return (num / 1e6).toFixed(1) + 'M';
    } else if (num >= 1e3) {
      return (num / 1e3).toFixed(1) + 'K';
    }
    return Math.round(num).toString();
  };

  // Inshorts-style Article Card
  const InshortsCard = ({ article }) => {
    const IconComponent = CATEGORY_ICONS[article.category] || BookOpen;
    const categoryColor = CATEGORY_COLORS[article.category] || 'from-gray-500 to-gray-600';

    return (
      <div className="bg-white border-b border-gray-200 last:border-b-0">
        {/* Image Section */}
        {article.image_url && (
          <div className="relative h-64 overflow-hidden">
            <img
              src={article.image_url}
              alt={article.headline || article.title}
              className="w-full h-full object-cover"
              onError={(e) => {
                e.target.style.display = 'none';
              }}
            />
            <div className={`absolute top-4 left-4 px-3 py-1 rounded-full bg-gradient-to-r ${categoryColor} text-white text-sm font-medium flex items-center gap-1`}>
              <IconComponent size={14} />
              {article.category}
            </div>
          </div>
        )}
        
        {/* Content Section */}
        <div className="p-6">
          {/* Clickable Headline */}
          <h2 
            onClick={() => window.open(article.url, '_blank')}
            className="text-xl font-bold text-gray-900 cursor-pointer hover:text-blue-600 transition-colors mb-3 leading-tight"
          >
            {article.headline || article.title}
          </h2>

          {/* Brief Summary */}
          <p className="text-gray-700 text-base leading-relaxed mb-4">
            {article.summary}
          </p>

          {/* Bottom Section */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4 text-sm text-gray-500">
              <span className="flex items-center gap-1">
                <Calendar size={14} />
                {formatDate(article.published_at)}
              </span>
              <span>{article.source}</span>
            </div>
            
            <button
              onClick={() => window.open(article.url, '_blank')}
              className="flex items-center gap-1 text-blue-600 hover:text-blue-700 font-medium text-sm transition-colors"
            >
              Read Full Article
              <ChevronRight size={16} />
            </button>
          </div>

          {/* Keywords */}
          {article.keywords && article.keywords.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-4">
              {article.keywords.slice(0, 4).map((keyword, index) => (
                <span
                  key={index}
                  className="px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded-full"
                >
                  {keyword}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  };

  const StockCard = ({ stock }) => {
    const isPositive = stock.percent_change >= 0;
    const TrendIcon = isPositive ? TrendingUp : TrendingDown;
    
    return (
      <div className="bg-white rounded-2xl shadow-lg hover:shadow-xl transition-all duration-300 transform hover:-translate-y-1 p-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h3 className="text-xl font-bold text-gray-900">{stock.symbol}</h3>
            <p className="text-sm text-gray-600 line-clamp-1">{stock.name}</p>
          </div>
          <div className={`flex items-center gap-1 px-2 py-1 rounded-full text-sm font-medium ${
            isPositive 
              ? 'bg-green-100 text-green-800' 
              : 'bg-red-100 text-red-800'
          }`}>
            <TrendIcon size={14} />
            {stock.percent_change.toFixed(2)}%
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-sm text-gray-500">Current Price</p>
            <p className="text-lg font-semibold text-gray-900">{formatPrice(stock.current_price)}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Change</p>
            <p className={`text-lg font-semibold ${
              isPositive ? 'text-green-600' : 'text-red-600'
            }`}>
              {isPositive ? '+' : ''}{formatPrice(stock.price_change)}
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Volume</p>
            <p className="text-sm font-medium text-gray-700">{formatNumber(stock.volume)}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Market Cap</p>
            <p className="text-sm font-medium text-gray-700">
              {stock.market_cap ? `$${formatNumber(stock.market_cap)}` : 'N/A'}
            </p>
          </div>
        </div>
      </div>
    );
  };

  const StatusBar = () => (
    <div className="bg-white rounded-2xl shadow-lg p-4 mb-6">
      <div className="flex flex-col lg:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <Activity size={16} className="text-green-500" />
            <span className="font-medium">System Status:</span>
            <span className="text-green-600">Active</span>
          </div>
          
          {systemStatus && (
            <>
              <div className="flex items-center gap-2 text-sm text-gray-600">
                <Clock size={16} />
                <span>News Update:</span>
                <span className="font-medium">{getTimeSince(systemStatus.last_news_update)}</span>
              </div>
              
              <div className="flex items-center gap-2 text-sm text-gray-600">
                <BookOpen size={16} />
                <span>Articles:</span>
                <span className="font-medium">{systemStatus.total_articles}</span>
              </div>

              <div className="flex items-center gap-2 text-sm text-gray-600">
                <BarChart3 size={16} />
                <span>Stocks:</span>
                <span className="font-medium">{systemStatus.total_stocks}</span>
              </div>
            </>
          )}
        </div>
        
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <span>Real-time updates • RSS feeds • Stock data</span>
          <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
        </div>
      </div>

      {/* Top Gainers/Losers Quick View */}
      {systemStatus && systemStatus.top_gainers && systemStatus.top_losers && (
        <div className="mt-4 pt-4 border-t border-gray-200">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <h4 className="text-sm font-semibold text-green-600 mb-2 flex items-center gap-1">
                <TrendingUp size={14} />
                Top Gainers
              </h4>
              <div className="space-y-1">
                {systemStatus.top_gainers.slice(0, 3).map((stock, index) => (
                  <div key={index} className="flex justify-between items-center text-xs">
                    <span className="font-medium">{stock.symbol}</span>
                    <span className="text-green-600">+{stock.percent_change.toFixed(2)}%</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <h4 className="text-sm font-semibold text-red-600 mb-2 flex items-center gap-1">
                <TrendingDown size={14} />
                Top Losers
              </h4>
              <div className="space-y-1">
                {systemStatus.top_losers.slice(0, 3).map((stock, index) => (
                  <div key={index} className="flex justify-between items-center text-xs">
                    <span className="font-medium">{stock.symbol}</span>
                    <span className="text-red-600">{stock.percent_change.toFixed(2)}%</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-50">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-gradient-to-r from-blue-500 to-indigo-600 rounded-xl">
                <Microscope className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">BioNews</h1>
                <p className="text-sm text-gray-500">Biotech news in 60 seconds</p>
              </div>
            </div>
            
            {/* Tab Navigation */}
            <div className="flex items-center gap-4">
              <div className="flex items-center bg-gray-100 rounded-xl p-1">
                <button
                  onClick={() => setCurrentTab('news')}
                  className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                    currentTab === 'news' 
                      ? 'bg-white shadow-md text-blue-600' 
                      : 'text-gray-500 hover:text-gray-700'
                  }`}
                >
                  News
                </button>
                <button
                  onClick={() => setCurrentTab('stocks')}
                  className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                    currentTab === 'stocks' 
                      ? 'bg-white shadow-md text-blue-600' 
                      : 'text-gray-500 hover:text-gray-700'
                  }`}
                >
                  Stocks
                </button>
              </div>
              
              <button
                onClick={currentTab === 'news' ? refreshArticles : refreshStocks}
                disabled={refreshing}
                className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-xl hover:bg-blue-600 transition-colors disabled:opacity-50"
              >
                <RefreshCw size={16} className={refreshing ? 'animate-spin' : ''} />
                {refreshing ? 'Updating...' : 'Refresh'}
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Status Bar */}
        <StatusBar />

        {/* Content based on current tab */}
        {currentTab === 'news' ? (
          <>
            {/* Search and Filters */}
            <div className="bg-white rounded-2xl shadow-lg p-6 mb-8">
              <div className="flex flex-col lg:flex-row gap-4">
                {/* Search */}
                <div className="flex-1">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={20} />
                    <input
                      type="text"
                      placeholder="Search biotech news, drugs, companies..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && searchArticles()}
                      className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>
                </div>

                {/* Category Filter */}
                <div className="flex items-center gap-4">
                  <select
                    value={selectedCategory}
                    onChange={(e) => handleCategoryChange(e.target.value)}
                    className="px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value="">All Categories</option>
                    {categories.map((category) => (
                      <option key={category} value={category}>
                        {category}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            {/* Inshorts-style News Feed */}
            {loading ? (
              <div className="flex items-center justify-center py-20">
                <div className="flex items-center gap-3 text-blue-600">
                  <RefreshCw size={24} className="animate-spin" />
                  <span className="text-lg font-medium">Loading latest news...</span>
                </div>
              </div>
            ) : articles.length === 0 ? (
              <div className="text-center py-20">
                <Microscope size={64} className="mx-auto text-gray-400 mb-4" />
                <h3 className="text-xl font-semibold text-gray-600 mb-2">No articles found</h3>
                <p className="text-gray-500">Try adjusting your search or filter criteria, or refresh to get the latest articles.</p>
              </div>
            ) : (
              <div className="bg-white rounded-2xl shadow-lg overflow-hidden">
                {articles.map((article, index) => (
                  <InshortsCard key={article.id} article={article} />
                ))}
              </div>
            )}
          </>
        ) : (
          <>
            {/* Stock Filters */}
            <div className="bg-white rounded-2xl shadow-lg p-6 mb-8">
              <div className="flex flex-col lg:flex-row items-center justify-between gap-4">
                <div className="flex items-center gap-4">
                  <h2 className="text-lg font-semibold text-gray-900">Biotech & Pharma Stocks</h2>
                  <div className="flex items-center bg-gray-100 rounded-xl p-1">
                    <button
                      onClick={() => handleStockViewChange('all')}
                      className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                        stockView === 'all' ? 'bg-white shadow-md text-blue-600' : 'text-gray-500'
                      }`}
                    >
                      All Stocks
                    </button>
                    <button
                      onClick={() => handleStockViewChange('gainers')}
                      className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                        stockView === 'gainers' ? 'bg-white shadow-md text-green-600' : 'text-gray-500'
                      }`}
                    >
                      Top Gainers
                    </button>
                    <button
                      onClick={() => handleStockViewChange('losers')}
                      className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                        stockView === 'losers' ? 'bg-white shadow-md text-red-600' : 'text-gray-500'
                      }`}
                    >
                      Top Losers
                    </button>
                  </div>
                </div>
                
                <div className="text-sm text-gray-500">
                  Updated: {systemStatus ? getTimeSince(systemStatus.last_stock_update) : 'Loading...'}
                </div>
              </div>
            </div>

            {/* Stocks Content */}
            {stocksLoading ? (
              <div className="flex items-center justify-center py-20">
                <div className="flex items-center gap-3 text-blue-600">
                  <RefreshCw size={24} className="animate-spin" />
                  <span className="text-lg font-medium">Loading stock data...</span>
                </div>
              </div>
            ) : stocks.length === 0 ? (
              <div className="text-center py-20">
                <BarChart3 size={64} className="mx-auto text-gray-400 mb-4" />
                <h3 className="text-xl font-semibold text-gray-600 mb-2">No stock data available</h3>
                <p className="text-gray-500">Try refreshing to get the latest stock information.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                {stocks.map((stock) => (
                  <StockCard key={stock.symbol} stock={stock} />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default App;