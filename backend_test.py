import requests
import sys
import json
from datetime import datetime

class BiotechNewsAPITester:
    def __init__(self, base_url="https://quickbioinfo.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, success, details=""):
        """Log test results"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name} - PASSED")
        else:
            print(f"❌ {name} - FAILED: {details}")
        
        self.test_results.append({
            "name": name,
            "success": success,
            "details": details
        })

    def run_test(self, name, method, endpoint, expected_status, data=None, params=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)
            
            success = response.status_code == expected_status
            
            if success:
                try:
                    response_data = response.json()
                    print(f"   Status: {response.status_code}")
                    print(f"   Response keys: {list(response_data.keys()) if isinstance(response_data, dict) else 'List with ' + str(len(response_data)) + ' items'}")
                    self.log_test(name, True)
                    return True, response_data
                except json.JSONDecodeError:
                    self.log_test(name, False, f"Invalid JSON response. Status: {response.status_code}")
                    return False, {}
            else:
                error_msg = f"Expected {expected_status}, got {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f" - {error_detail}"
                except:
                    error_msg += f" - {response.text[:200]}"
                self.log_test(name, False, error_msg)
                return False, {}

        except requests.exceptions.RequestException as e:
            self.log_test(name, False, f"Request error: {str(e)}")
            return False, {}
        except Exception as e:
            self.log_test(name, False, f"Unexpected error: {str(e)}")
            return False, {}

    def test_root_endpoint(self):
        """Test root API endpoint"""
        return self.run_test("Root API Endpoint", "GET", "", 200)

    def test_get_categories(self):
        """Test getting all categories"""
        success, response = self.run_test("Get Categories", "GET", "categories", 200)
        if success and 'categories' in response:
            categories = response['categories']
            expected_categories = [
                "Academic Research", "Industry Updates", "Early Discovery",
                "Clinical Trials", "Drug Modalities", "Healthcare & Policy"
            ]
            if all(cat in categories for cat in expected_categories):
                print(f"   ✓ All expected categories found: {categories}")
                return True, response
            else:
                self.log_test("Categories Content Validation", False, f"Missing expected categories. Got: {categories}")
        return success, response

    def test_get_articles(self):
        """Test getting all articles"""
        success, response = self.run_test("Get All Articles", "GET", "articles", 200)
        if success and isinstance(response, list):
            print(f"   ✓ Retrieved {len(response)} articles")
            if len(response) > 0:
                article = response[0]
                required_fields = ['id', 'title', 'summary', 'content', 'category', 'source', 'url', 'published_at']
                missing_fields = [field for field in required_fields if field not in article]
                if missing_fields:
                    self.log_test("Article Structure Validation", False, f"Missing fields: {missing_fields}")
                else:
                    print(f"   ✓ Article structure is valid")
                    return True, response
        return success, response

    def test_get_articles_by_category(self):
        """Test getting articles filtered by category"""
        success, response = self.run_test(
            "Get Articles by Category", 
            "GET", 
            "articles", 
            200, 
            params={"category": "Clinical Trials"}
        )
        if success and isinstance(response, list):
            if len(response) > 0:
                # Check if all articles belong to the requested category
                clinical_articles = [a for a in response if a.get('category') == 'Clinical Trials']
                if len(clinical_articles) == len(response):
                    print(f"   ✓ All {len(response)} articles are from Clinical Trials category")
                else:
                    self.log_test("Category Filter Validation", False, f"Some articles don't match category filter")
        return success, response

    def test_get_single_article(self, article_id=None):
        """Test getting a single article by ID"""
        if not article_id:
            # First get articles to get an ID
            success, articles = self.test_get_articles()
            if not success or not articles:
                self.log_test("Get Single Article", False, "No articles available to test with")
                return False, {}
            article_id = articles[0]['id']
        
        return self.run_test("Get Single Article", "GET", f"articles/{article_id}", 200)

    def test_system_status(self):
        """Test new system status endpoint"""
        success, response = self.run_test("System Status", "GET", "status", 200)
        if success:
            required_fields = ['last_update', 'total_articles', 'articles_by_category']
            missing_fields = [field for field in required_fields if field not in response]
            if missing_fields:
                self.log_test("Status Response Validation", False, f"Missing fields: {missing_fields}")
            else:
                print(f"   ✓ Last update: {response['last_update']}")
                print(f"   ✓ Total articles: {response['total_articles']}")
                print(f"   ✓ Articles by category: {response['articles_by_category']}")
                return True, response
        return success, response

    def test_refresh_articles(self):
        """Test refreshing articles (this triggers real news fetching and LLM summarization)"""
        print("\n🔄 Testing article refresh with real news APIs (this may take 60+ seconds)...")
        print("   This tests: PubMed, NewsAPI, ClinicalTrials.gov integration + LLM summarization")
        success, response = self.run_test("Refresh Articles", "POST", "articles/refresh", 200)
        if success:
            required_fields = ['message', 'total_fetched', 'last_update']
            missing_fields = [field for field in required_fields if field not in response]
            if missing_fields:
                self.log_test("Refresh Response Validation", False, f"Missing fields: {missing_fields}")
            else:
                print(f"   ✓ Refresh completed: {response['message']}")
                print(f"   ✓ Total fetched: {response['total_fetched']}")
                print(f"   ✓ Last update timestamp: {response['last_update']}")
                return True, response
        return success, response

    def test_real_news_integration(self):
        """Test that articles are coming from real news sources"""
        success, articles = self.test_get_articles()
        if not success or not articles:
            return False, {}
        
        # Check for real news sources
        real_sources = set()
        categories_found = set()
        keywords_found = []
        
        for article in articles[:10]:  # Check first 10 articles
            source = article.get('source', '')
            category = article.get('category', '')
            keywords = article.get('keywords', [])
            
            real_sources.add(source)
            categories_found.add(category)
            keywords_found.extend(keywords)
        
        # Expected real sources
        expected_sources = ['PubMed', 'NewsAPI', 'ClinicalTrials.gov']
        found_real_sources = [src for src in expected_sources if any(expected in source for expected in [src, src.lower()])]
        
        print(f"   ✓ Real sources found: {list(real_sources)}")
        print(f"   ✓ Categories found: {list(categories_found)}")
        print(f"   ✓ Sample keywords: {keywords_found[:10]}")
        
        if len(found_real_sources) > 0:
            self.log_test("Real News Sources", True, f"Found sources from: {found_real_sources}")
            return True, articles
        else:
            self.log_test("Real News Sources", False, f"No real news sources found. Sources: {list(real_sources)}")
            return False, articles

    def test_search_articles(self):
        """Test searching articles"""
        search_queries = [
            {"query": "CAR-T", "category": None, "limit": 20},
            {"query": "CRISPR", "category": "Drug Modalities", "limit": 10},
            {"query": "clinical", "category": None, "limit": 5}
        ]
        
        all_success = True
        for i, query in enumerate(search_queries):
            success, response = self.run_test(
                f"Search Articles - Query {i+1} ({query['query']})", 
                "POST", 
                "search", 
                200, 
                data=query
            )
            if success and isinstance(response, list):
                print(f"   ✓ Search for '{query['query']}' returned {len(response)} results")
            else:
                all_success = False
        
        return all_success, {}

    def test_user_preferences(self):
        """Test user preferences endpoints"""
        test_user_id = f"test_user_{datetime.now().strftime('%H%M%S')}"
        test_categories = ["Clinical Trials", "Drug Modalities"]
        
        # Test saving preferences
        success1, response1 = self.run_test(
            "Save User Preferences", 
            "POST", 
            f"preferences?user_id={test_user_id}", 
            200,
            data=test_categories
        )
        
        if not success1:
            return False, {}
        
        # Test getting preferences
        success2, response2 = self.run_test(
            "Get User Preferences", 
            "GET", 
            f"preferences/{test_user_id}", 
            200
        )
        
        if success2 and 'preferred_categories' in response2:
            saved_categories = response2['preferred_categories']
            if set(saved_categories) == set(test_categories):
                print(f"   ✓ Preferences saved and retrieved correctly: {saved_categories}")
                return True, response2
            else:
                self.log_test("Preferences Validation", False, f"Saved categories don't match. Expected: {test_categories}, Got: {saved_categories}")
        
        return success2, response2

    def test_error_handling(self):
        """Test error handling for invalid requests"""
        # Test invalid article ID
        success1, _ = self.run_test("Invalid Article ID", "GET", "articles/invalid-id", 404)
        
        # Test invalid category filter
        success2, _ = self.run_test(
            "Invalid Category Filter", 
            "GET", 
            "articles", 
            200, 
            params={"category": "InvalidCategory"}
        )
        
        return success1 and success2, {}

    def run_all_tests(self):
        """Run all API tests"""
        print("🧪 Starting Biotech News API Testing...")
        print(f"🌐 Base URL: {self.base_url}")
        print("=" * 60)
        
        # Test basic connectivity
        self.test_root_endpoint()
        
        # Test core functionality
        self.test_get_categories()
        self.test_get_articles()
        self.test_get_articles_by_category()
        self.test_get_single_article()
        
        # Test search functionality
        self.test_search_articles()
        
        # Test user preferences
        self.test_user_preferences()
        
        # Test LLM integration (refresh articles)
        self.test_refresh_articles()
        
        # Test error handling
        self.test_error_handling()
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run)*100:.1f}%")
        
        # Print failed tests
        failed_tests = [test for test in self.test_results if not test['success']]
        if failed_tests:
            print("\n❌ FAILED TESTS:")
            for test in failed_tests:
                print(f"   • {test['name']}: {test['details']}")
        
        return self.tests_passed == self.tests_run

def main():
    tester = BiotechNewsAPITester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())