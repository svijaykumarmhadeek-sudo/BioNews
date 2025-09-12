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
          <div className="flex-1 min-w-0">
            <h3 className="text-xl font-bold text-gray-900 truncate">{stock.symbol}</h3>
            <p className="text-sm text-gray-600 truncate">{stock.name}</p>
          </div>
          <div className={`flex items-center gap-1 px-2 py-1 rounded-full text-sm font-medium ml-2 flex-shrink-0 ${
            isPositive 
              ? 'bg-green-100 text-green-800' 
              : 'bg-red-100 text-red-800'
          }`}>
            <TrendIcon size={14} />
            {stock.percent_change.toFixed(2)}%
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="min-w-0">
            <p className="text-sm text-gray-500">Current Price</p>
            <p className="text-lg font-semibold text-gray-900 truncate">{formatPrice(stock.current_price)}</p>
          </div>
          <div className="min-w-0">
            <p className="text-sm text-gray-500">Change</p>
            <p className={`text-lg font-semibold truncate ${
              isPositive ? 'text-green-600' : 'text-red-600'
            }`}>
              {isPositive ? '+' : ''}{formatPrice(stock.price_change)}
            </p>
          </div>
          <div className="min-w-0">
            <p className="text-sm text-gray-500">Volume</p>
            <p className="text-sm font-medium text-gray-700 truncate">{formatNumber(stock.volume)}</p>
          </div>
          <div className="min-w-0">
            <p className="text-sm text-gray-500">Market Cap</p>
            <p className="text-sm font-medium text-gray-700 truncate">
              {stock.market_cap ? `$${formatNumber(stock.market_cap)}` : 'N/A'}
            </p>
          </div>
        </div>
      </div>
    );
  };

  const StatusBar = () => (
    <div className="bg-white/80 backdrop-blur-lg rounded-3xl shadow-xl border border-white/20 p-8 mb-8">
      {/* Main Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        {/* System Status */}
        <div className="flex flex-col items-center p-6 bg-gradient-to-br from-emerald-50 to-green-50 rounded-2xl border border-emerald-100">
          <div className="flex items-center justify-center w-12 h-12 bg-emerald-500 rounded-full mb-3">
            <Activity size={20} className="text-white" />
          </div>
          <h3 className="font-semibold text-gray-900 mb-1">System Status</h3>
          <p className="text-emerald-600 font-medium">Active</p>
        </div>

        {/* News Update */}
        {systemStatus && (
          <div className="flex flex-col items-center p-6 bg-gradient-to-br from-blue-50 to-indigo-50 rounded-2xl border border-blue-100">
            <div className="flex items-center justify-center w-12 h-12 bg-blue-500 rounded-full mb-3">
              <Clock size={20} className="text-white" />
            </div>
            <h3 className="font-semibold text-gray-900 mb-1">Last Update</h3>
            <p className="text-blue-600 font-medium text-center text-sm">{getTimeSince(systemStatus.last_news_update)}</p>
          </div>
        )}

        {/* Articles Count */}
        {systemStatus && (
          <div className="flex flex-col items-center p-6 bg-gradient-to-br from-purple-50 to-violet-50 rounded-2xl border border-purple-100">
            <div className="flex items-center justify-center w-12 h-12 bg-purple-500 rounded-full mb-3">
              <BookOpen size={20} className="text-white" />
            </div>
            <h3 className="font-semibold text-gray-900 mb-1">Articles</h3>
            <p className="text-purple-600 font-bold text-xl">{systemStatus.total_articles}</p>
          </div>
        )}

        {/* Stocks Count */}
        {systemStatus && (
          <div className="flex flex-col items-center p-6 bg-gradient-to-br from-orange-50 to-amber-50 rounded-2xl border border-orange-100">
            <div className="flex items-center justify-center w-12 h-12 bg-orange-500 rounded-full mb-3">
              <BarChart3 size={20} className="text-white" />
            </div>
            <h3 className="font-semibold text-gray-900 mb-1">Stocks</h3>
            <p className="text-orange-600 font-bold text-xl">{systemStatus.total_stocks}</p>
          </div>
        )}
      </div>

      {/* Live Status Indicator */}
      <div className="flex items-center justify-center mb-8">
        <div className="flex items-center gap-3 px-6 py-3 bg-gradient-to-r from-emerald-500 to-green-500 rounded-full text-white shadow-lg">
          <div className="w-3 h-3 bg-white rounded-full animate-pulse"></div>
          <span className="font-medium">Real-time updates • RSS feeds • Stock data</span>
        </div>
      </div>

      {/* Enhanced Top Gainers/Losers */}
      {systemStatus && systemStatus.top_gainers && systemStatus.top_losers && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Top Gainers */}
          <div className="bg-gradient-to-br from-emerald-50 to-green-50 rounded-2xl p-6 border border-emerald-100">
            <div className="flex items-center gap-3 mb-6">
              <div className="flex items-center justify-center w-10 h-10 bg-emerald-500 rounded-full">
                <TrendingUp size={18} className="text-white" />
              </div>
              <h4 className="text-lg font-bold text-emerald-700">Top Gainers</h4>
            </div>
            <div className="space-y-4">
              {systemStatus.top_gainers.slice(0, 3).map((stock, index) => (
                <div key={index} className="flex items-center justify-between p-4 bg-white/60 rounded-xl backdrop-blur-sm">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-emerald-100 rounded-full flex items-center justify-center">
                      <span className="text-emerald-600 font-bold text-sm">{index + 1}</span>
                    </div>
                    <span className="font-semibold text-gray-900">{stock.symbol}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-gray-600 text-sm">${stock.current_price}</span>
                    <span className="bg-emerald-500 text-white px-3 py-1 rounded-full text-sm font-medium">
                      +{stock.percent_change.toFixed(2)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Top Losers */}
          <div className="bg-gradient-to-br from-red-50 to-rose-50 rounded-2xl p-6 border border-red-100">
            <div className="flex items-center gap-3 mb-6">
              <div className="flex items-center justify-center w-10 h-10 bg-red-500 rounded-full">
                <TrendingDown size={18} className="text-white" />
              </div>
              <h4 className="text-lg font-bold text-red-700">Top Losers</h4>
            </div>
            <div className="space-y-4">
              {systemStatus.top_losers.slice(0, 3).map((stock, index) => (
                <div key={index} className="flex items-center justify-between p-4 bg-white/60 rounded-xl backdrop-blur-sm">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-red-100 rounded-full flex items-center justify-center">
                      <span className="text-red-600 font-bold text-sm">{index + 1}</span>
                    </div>
                    <span className="font-semibold text-gray-900">{stock.symbol}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-gray-600 text-sm">${stock.current_price}</span>
                    <span className="bg-red-500 text-white px-3 py-1 rounded-full text-sm font-medium">
                      {stock.percent_change.toFixed(2)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      {/* Header */}
      <header className="bg-white/90 backdrop-blur-lg shadow-lg border-b border-white/20 sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-20">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-gradient-to-br from-blue-500 via-indigo-500 to-purple-600 rounded-2xl shadow-lg">
                <Microscope className="w-8 h-8 text-white" />
              </div>
              <div>
                <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                  BioNews
                </h1>
                <p className="text-sm text-gray-600 font-medium">Biotech news in 60 seconds</p>
              </div>
            </div>
            
            {/* Tab Navigation */}
            <div className="flex items-center gap-6">
              <div className="flex items-center bg-white/60 backdrop-blur-sm rounded-2xl p-2 shadow-lg border border-white/30">
                <button
                  onClick={() => setCurrentTab('news')}
                  className={`px-6 py-3 rounded-xl font-semibold transition-all duration-300 ${
                    currentTab === 'news' 
                      ? 'bg-gradient-to-r from-blue-500 to-indigo-600 text-white shadow-lg transform scale-105' 
                      : 'text-gray-600 hover:text-blue-600 hover:bg-white/50'
                  }`}
                >
                  News
                </button>
                <button
                  onClick={() => setCurrentTab('stocks')}
                  className={`px-6 py-3 rounded-xl font-semibold transition-all duration-300 ${
                    currentTab === 'stocks' 
                      ? 'bg-gradient-to-r from-blue-500 to-indigo-600 text-white shadow-lg transform scale-105' 
                      : 'text-gray-600 hover:text-blue-600 hover:bg-white/50'
                  }`}
                >
                  Stocks
                </button>
              </div>
              
              <button
                onClick={currentTab === 'news' ? refreshArticles : refreshStocks}
                disabled={refreshing}
                className="flex items-center gap-3 px-6 py-3 bg-gradient-to-r from-emerald-500 to-green-500 text-white rounded-2xl hover:from-emerald-600 hover:to-green-600 transition-all duration-300 disabled:opacity-50 shadow-lg font-semibold transform hover:scale-105"
              >
                <RefreshCw size={18} className={refreshing ? 'animate-spin' : ''} />
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
            <div className="bg-white/80 backdrop-blur-lg rounded-3xl shadow-xl border border-white/20 p-8 mb-8">
              <div className="flex flex-col lg:flex-row gap-6">
                {/* Search */}
                <div className="flex-1">
                  <div className="relative">
                    <div className="absolute left-4 top-1/2 transform -translate-y-1/2">
                      <Search className="text-blue-400" size={22} />
                    </div>
                    <input
                      type="text"
                      placeholder="Search biotech news, drugs, companies..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && searchArticles()}
                      className="w-full pl-14 pr-6 py-4 bg-white/60 border border-blue-100 rounded-2xl focus:ring-4 focus:ring-blue-200 focus:border-blue-400 transition-all duration-300 placeholder-gray-500 font-medium shadow-inner"
                    />
                  </div>
                </div>

                {/* Category Filter */}
                <div className="flex items-center gap-4">
                  <select
                    value={selectedCategory}
                    onChange={(e) => handleCategoryChange(e.target.value)}
                    className="px-6 py-4 bg-white/60 border border-blue-100 rounded-2xl focus:ring-4 focus:ring-blue-200 focus:border-blue-400 transition-all duration-300 font-medium shadow-inner"
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