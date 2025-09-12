import React, { useState, useEffect } from 'react';
import { Search, Filter, Grid, List, Calendar, ExternalLink, RefreshCw, Heart, BookOpen, Microscope, Pill, Building2, Shield, Clock, Activity } from 'lucide-react';
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
  const [categories, setCategories] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState('card'); // 'card' or 'table'
  const [loading, setLoading] = useState(true);
  const [expandedCards, setExpandedCards] = useState(new Set());
  const [systemStatus, setSystemStatus] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    fetchCategories();
    fetchArticles();
    fetchSystemStatus();
  }, []);

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

  const refreshArticles = async () => {
    try {
      setRefreshing(true);
      const response = await axios.post(`${API}/articles/refresh`);
      
      // Show success message
      if (response.data.message) {
        console.log('Refresh result:', response.data.message);
      }
      
      // Refresh the articles and status
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

  const toggleCardExpansion = (articleId) => {
    const newExpanded = new Set(expandedCards);
    if (newExpanded.has(articleId)) {
      newExpanded.delete(articleId);
    } else {
      newExpanded.add(articleId);
    }
    setExpandedCards(newExpanded);
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  const formatDateTime = (dateString) => {
    return new Date(dateString).toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
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

  const ArticleCard = ({ article }) => {
    const isExpanded = expandedCards.has(article.id);
    const IconComponent = CATEGORY_ICONS[article.category] || BookOpen;
    const categoryColor = CATEGORY_COLORS[article.category] || 'from-gray-500 to-gray-600';

    return (
      <div className="bg-white rounded-2xl shadow-lg hover:shadow-xl transition-all duration-300 transform hover:-translate-y-1 overflow-hidden">
        {article.image_url && (
          <div className="relative h-48 overflow-hidden">
            <img
              src={article.image_url}
              alt={article.title}
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
        
        <div className="p-6">
          <div className="flex items-start justify-between mb-3">
            <h2 className="text-xl font-bold text-gray-900 line-clamp-2 leading-tight">
              {article.title}
            </h2>
            <button
              onClick={() => window.open(article.url, '_blank')}
              className="text-blue-500 hover:text-blue-700 transition-colors ml-2 flex-shrink-0"
            >
              <ExternalLink size={18} />
            </button>
          </div>

          <div className="flex items-center gap-4 text-sm text-gray-500 mb-4">
            <span className="flex items-center gap-1">
              <Calendar size={14} />
              {formatDate(article.published_at)}
            </span>
            <span>{article.source}</span>
          </div>

          <p className="text-gray-700 leading-relaxed mb-4">
            {article.summary}
          </p>

          {article.keywords && article.keywords.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-4">
              {article.keywords.map((keyword, index) => (
                <span
                  key={index}
                  className="px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded-full"
                >
                  {keyword}
                </span>
              ))}
            </div>
          )}

          <button
            onClick={() => toggleCardExpansion(article.id)}
            className="w-full py-2 text-blue-600 hover:text-blue-800 font-medium transition-colors"
          >
            {isExpanded ? 'Show Less' : 'Read More'}
          </button>

          {isExpanded && (
            <div className="mt-4 pt-4 border-t border-gray-200">
              <h3 className="font-semibold text-gray-900 mb-2">Full Article</h3>
              <p className="text-gray-700 leading-relaxed whitespace-pre-wrap">
                {article.content}
              </p>
            </div>
          )}
        </div>
      </div>
    );
  };

  const TableView = () => (
    <div className="bg-white rounded-2xl shadow-lg overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">Date</th>
              <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">Category</th>
              <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">Title</th>
              <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">Summary</th>
              <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">Source</th>
              <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">Keywords</th>
              <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">Link</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {articles.map((article) => (
              <tr key={article.id} className="hover:bg-gray-50 transition-colors">
                <td className="px-6 py-4 text-sm text-gray-600">
                  {formatDate(article.published_at)}
                </td>
                <td className="px-6 py-4">
                  <div className={`inline-flex items-center gap-1 px-2 py-1 rounded-full bg-gradient-to-r ${CATEGORY_COLORS[article.category] || 'from-gray-500 to-gray-600'} text-white text-xs`}>
                    {React.createElement(CATEGORY_ICONS[article.category] || BookOpen, { size: 12 })}
                    {article.category}
                  </div>
                </td>
                <td className="px-6 py-4 text-sm font-medium text-gray-900 max-w-xs">
                  <div className="line-clamp-2">{article.title}</div>
                </td>
                <td className="px-6 py-4 text-sm text-gray-700 max-w-md">
                  <div className="line-clamp-3">{article.summary}</div>
                </td>
                <td className="px-6 py-4 text-sm text-gray-600">{article.source}</td>
                <td className="px-6 py-4">
                  <div className="flex flex-wrap gap-1 max-w-xs">
                    {article.keywords?.slice(0, 3).map((keyword, index) => (
                      <span
                        key={index}
                        className="px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded-full"
                      >
                        {keyword}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-6 py-4">
                  <button
                    onClick={() => window.open(article.url, '_blank')}
                    className="text-blue-500 hover:text-blue-700 transition-colors"
                  >
                    <ExternalLink size={16} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );

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
                <span>Last Update:</span>
                <span className="font-medium">{getTimeSince(systemStatus.last_update)}</span>
              </div>
              
              <div className="flex items-center gap-2 text-sm text-gray-600">
                <BookOpen size={16} />
                <span>Total Articles:</span>
                <span className="font-medium">{systemStatus.total_articles}</span>
              </div>
            </>
          )}
        </div>
        
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <span>Auto-updates every 12 hours</span>
          <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-gradient-to-r from-blue-500 to-indigo-600 rounded-xl">
                <Microscope className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">BioNews</h1>
                <p className="text-sm text-gray-500">Real-time Biotech & Pharma Research Updates</p>
              </div>
            </div>
            
            <button
              onClick={refreshArticles}
              disabled={refreshing}
              className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-xl hover:bg-blue-600 transition-colors disabled:opacity-50"
            >
              <RefreshCw size={16} className={refreshing ? 'animate-spin' : ''} />
              {refreshing ? 'Updating...' : 'Refresh'}
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Status Bar */}
        <StatusBar />

        {/* Search and Filters */}
        <div className="bg-white rounded-2xl shadow-lg p-6 mb-8">
          <div className="flex flex-col lg:flex-row gap-4">
            {/* Search */}
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={20} />
                <input
                  type="text"
                  placeholder="Search articles, keywords, compounds..."
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

              {/* View Toggle */}
              <div className="flex items-center bg-gray-100 rounded-xl p-1">
                <button
                  onClick={() => setViewMode('card')}
                  className={`p-2 rounded-lg transition-colors ${
                    viewMode === 'card' ? 'bg-white shadow-md text-blue-600' : 'text-gray-500'
                  }`}
                >
                  <Grid size={18} />
                </button>
                <button
                  onClick={() => setViewMode('table')}
                  className={`p-2 rounded-lg transition-colors ${
                    viewMode === 'table' ? 'bg-white shadow-md text-blue-600' : 'text-gray-500'
                  }`}
                >
                  <List size={18} />
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Content */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="flex items-center gap-3 text-blue-600">
              <RefreshCw size={24} className="animate-spin" />
              <span className="text-lg font-medium">Loading latest articles...</span>
            </div>
          </div>
        ) : articles.length === 0 ? (
          <div className="text-center py-20">
            <Microscope size={64} className="mx-auto text-gray-400 mb-4" />
            <h3 className="text-xl font-semibold text-gray-600 mb-2">No articles found</h3>
            <p className="text-gray-500">Try adjusting your search or filter criteria, or refresh to get the latest articles.</p>
          </div>
        ) : viewMode === 'card' ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {articles.map((article) => (
              <ArticleCard key={article.id} article={article} />
            ))}
          </div>
        ) : (
          <TableView />
        )}
      </div>
    </div>
  );
}

export default App;