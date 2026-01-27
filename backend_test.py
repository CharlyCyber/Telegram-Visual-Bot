#!/usr/bin/env python3
"""
Comprehensive test suite for the Telegram Movie/Series Bot
Tests all APIs, bot functionality, and message formatting
"""

import asyncio
import httpx
import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class TelegramBotTester:
    def __init__(self):
        self.bot_token = os.getenv("BOT_TOKEN")
        self.tmdb_api_key = os.getenv("TMDB_API_KEY")
        self.omdb_api_key = os.getenv("OMDB_API_KEY")
        self.chat_id = -1002700094661
        
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        
        print("🤖 Telegram Movie Bot Test Suite")
        print("=" * 50)
        print(f"Bot Token: {'✅ Set' if self.bot_token else '❌ Missing'}")
        print(f"TMDb API Key: {'✅ Set' if self.tmdb_api_key else '❌ Missing'}")
        print(f"OMDb API Key: {'✅ Set' if self.omdb_api_key else '❌ Missing'}")
        print(f"Target Chat ID: {self.chat_id}")
        print("=" * 50)

    def log_test(self, name, success, details=""):
        """Log test results"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            status = "✅ PASS"
        else:
            status = "❌ FAIL"
        
        result = f"{status} - {name}"
        if details:
            result += f" | {details}"
        
        print(result)
        self.test_results.append({
            'name': name,
            'success': success,
            'details': details
        })
        return success

    async def test_telegram_bot_api(self):
        """Test if Telegram Bot API is accessible"""
        try:
            async with httpx.AsyncClient() as client:
                url = f"https://api.telegram.org/bot{self.bot_token}/getMe"
                response = await client.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    bot_info = data.get('result', {})
                    username = bot_info.get('username', 'Unknown')
                    return self.log_test("Telegram Bot API Connection", True, f"Bot: @{username}")
                else:
                    return self.log_test("Telegram Bot API Connection", False, f"Status: {response.status_code}")
                    
        except Exception as e:
            return self.log_test("Telegram Bot API Connection", False, f"Error: {str(e)}")

    async def test_tmdb_api(self):
        """Test TMDb API with movie and TV search"""
        try:
            async with httpx.AsyncClient() as client:
                # Test movie search
                movie_url = f'https://api.themoviedb.org/3/search/movie?api_key={self.tmdb_api_key}&query=Inception&language=es-ES'
                movie_response = await client.get(movie_url, timeout=10)
                
                # Test TV search
                tv_url = f'https://api.themoviedb.org/3/search/tv?api_key={self.tmdb_api_key}&query=Breaking Bad&language=es-ES'
                tv_response = await client.get(tv_url, timeout=10)
                
                movie_success = movie_response.status_code == 200 and len(movie_response.json().get('results', [])) > 0
                tv_success = tv_response.status_code == 200 and len(tv_response.json().get('results', [])) > 0
                
                if movie_success and tv_success:
                    movie_count = len(movie_response.json().get('results', []))
                    tv_count = len(tv_response.json().get('results', []))
                    return self.log_test("TMDb API (Movies & TV)", True, f"Movies: {movie_count}, TV: {tv_count}")
                else:
                    return self.log_test("TMDb API (Movies & TV)", False, f"Movie: {movie_success}, TV: {tv_success}")
                    
        except Exception as e:
            return self.log_test("TMDb API (Movies & TV)", False, f"Error: {str(e)}")

    async def test_tvmaze_api(self):
        """Test TVmaze API"""
        try:
            async with httpx.AsyncClient() as client:
                url = "https://api.tvmaze.com/search/shows?q=Breaking Bad"
                response = await client.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if data and len(data) > 0:
                        show_name = data[0]['show'].get('name', 'Unknown')
                        return self.log_test("TVmaze API", True, f"Found: {show_name}")
                    else:
                        return self.log_test("TVmaze API", False, "No results found")
                else:
                    return self.log_test("TVmaze API", False, f"Status: {response.status_code}")
                    
        except Exception as e:
            return self.log_test("TVmaze API", False, f"Error: {str(e)}")

    async def test_omdb_api(self):
        """Test OMDb API if key is available"""
        if not self.omdb_api_key:
            return self.log_test("OMDb API", False, "API key not configured")
            
        try:
            async with httpx.AsyncClient() as client:
                url = f"https://www.omdbapi.com/?t=Inception&apikey={self.omdb_api_key}"
                response = await client.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('Response') == 'True':
                        title = data.get('Title', 'Unknown')
                        return self.log_test("OMDb API", True, f"Found: {title}")
                    else:
                        return self.log_test("OMDb API", False, f"API Response: {data.get('Error', 'Unknown error')}")
                else:
                    return self.log_test("OMDb API", False, f"Status: {response.status_code}")
                    
        except Exception as e:
            return self.log_test("OMDb API", False, f"Error: {str(e)}")

    async def test_bot_message_formatting(self):
        """Test message formatting functions"""
        try:
            # Import bot functions for testing
            sys.path.append('/app')
            from bot import get_genre_emojis, get_keyword_emojis, get_synopsis_with_emojis, get_dynamic_closing
            
            # Test genre emojis
            genres = ['Acción', 'Comedia', 'Drama']
            genre_emojis = get_genre_emojis(genres)
            
            # Test keyword emojis
            title = "Luna de Miel en el Espacio"
            keyword_emojis = get_keyword_emojis(title)
            
            # Test synopsis with emojis
            synopsis = "Una historia de amor y misterio en el espacio"
            synopsis_with_emojis = get_synopsis_with_emojis(synopsis)
            
            # Test dynamic closing
            closing = get_dynamic_closing(synopsis)
            
            success = all([
                genre_emojis and len(genre_emojis) > 0,
                keyword_emojis and len(keyword_emojis) > 0,
                synopsis_with_emojis and len(synopsis_with_emojis) > len(synopsis),
                closing and len(closing) > 0
            ])
            
            return self.log_test("Message Formatting Functions", success, 
                               f"Emojis: {len(genre_emojis.split())} genre, {len(keyword_emojis.split())} keyword")
            
        except Exception as e:
            return self.log_test("Message Formatting Functions", False, f"Error: {str(e)}")

    async def test_tmdb_detailed_search(self):
        """Test detailed TMDb search with specific movies"""
        test_cases = [
            ("Inception 2010", "unique result"),
            ("Batman", "multiple results"),
            ("NonExistentMovie12345", "no results")
        ]
        
        results = []
        
        for query, expected in test_cases:
            try:
                async with httpx.AsyncClient() as client:
                    movie_url = f'https://api.themoviedb.org/3/search/movie?api_key={self.tmdb_api_key}&query={query}&language=es-ES'
                    tv_url = f'https://api.themoviedb.org/3/search/tv?api_key={self.tmdb_api_key}&query={query}&language=es-ES'
                    
                    movie_response, tv_response = await asyncio.gather(
                        client.get(movie_url, timeout=10),
                        client.get(tv_url, timeout=10)
                    )
                    
                    movie_results = movie_response.json().get('results', [])
                    tv_results = tv_response.json().get('results', [])
                    total_results = len(movie_results) + len(tv_results)
                    
                    if expected == "unique result":
                        success = total_results == 1
                    elif expected == "multiple results":
                        success = total_results > 1
                    elif expected == "no results":
                        success = total_results == 0
                    else:
                        success = False
                    
                    results.append(success)
                    self.log_test(f"TMDb Search: '{query}'", success, f"Results: {total_results} ({expected})")
                    
            except Exception as e:
                results.append(False)
                self.log_test(f"TMDb Search: '{query}'", False, f"Error: {str(e)}")
        
        return all(results)

    async def test_bot_webhook_status(self):
        """Test bot webhook status"""
        try:
            async with httpx.AsyncClient() as client:
                url = f"https://api.telegram.org/bot{self.bot_token}/getWebhookInfo"
                response = await client.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    webhook_info = data.get('result', {})
                    webhook_url = webhook_info.get('url', '')
                    
                    # For polling bots, webhook should be empty
                    if not webhook_url:
                        return self.log_test("Bot Webhook Status", True, "Polling mode (no webhook)")
                    else:
                        return self.log_test("Bot Webhook Status", True, f"Webhook: {webhook_url}")
                else:
                    return self.log_test("Bot Webhook Status", False, f"Status: {response.status_code}")
                    
        except Exception as e:
            return self.log_test("Bot Webhook Status", False, f"Error: {str(e)}")

    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 50)
        print("📊 TEST SUMMARY")
        print("=" * 50)
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%" if self.tests_run > 0 else "0%")
        
        if self.tests_passed < self.tests_run:
            print("\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result['success']:
                    print(f"  - {result['name']}: {result['details']}")
        
        print("\n🎯 RECOMMENDATIONS:")
        if self.tests_passed == self.tests_run:
            print("  ✅ All tests passed! Bot is ready for use.")
        else:
            print("  🔧 Fix the failed tests before deploying the bot.")
            if not self.omdb_api_key:
                print("  💡 Consider adding OMDb API key for better movie search coverage.")

async def main():
    """Run all tests"""
    tester = TelegramBotTester()
    
    # Run all tests
    await tester.test_telegram_bot_api()
    await tester.test_tmdb_api()
    await tester.test_tvmaze_api()
    await tester.test_omdb_api()
    await tester.test_bot_webhook_status()
    await tester.test_tmdb_detailed_search()
    await tester.test_bot_message_formatting()
    
    # Print summary
    tester.print_summary()
    
    # Return exit code
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)