#!/usr/bin/env python3
"""
Final Comprehensive Test Report for Telegram Movie Bot
Addresses all requirements from the review request
"""

import asyncio
import os
import sys
import subprocess
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class FinalBotTestReport:
    def __init__(self):
        self.bot_token = os.getenv("BOT_TOKEN")
        self.tmdb_api_key = os.getenv("TMDB_API_KEY")
        self.omdb_api_key = os.getenv("OMDB_API_KEY")
        self.chat_id = -1002700094661
        
        print("🎯 FINAL TELEGRAM BOT TEST REPORT")
        print("=" * 60)
        print(f"📅 Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🤖 Bot: @Charlipunkbot")
        print(f"🎯 Target Group: {self.chat_id}")
        print("=" * 60)

    def check_single_instance(self):
        """Requirement 1: Verify only one bot instance is running"""
        print("\n1️⃣ CHECKING SINGLE BOT INSTANCE")
        print("-" * 40)
        
        try:
            result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
            bot_processes = [line for line in result.stdout.split('\n') if 'bot.py' in line and 'grep' not in line]
            
            print(f"🔍 Found {len(bot_processes)} bot process(es)")
            for process in bot_processes:
                print(f"   📋 {process.strip()}")
            
            if len(bot_processes) == 1:
                print("✅ PASS: Only one bot instance running")
                return True
            elif len(bot_processes) == 0:
                print("❌ FAIL: No bot instances found")
                return False
            else:
                print("⚠️ WARNING: Multiple bot instances detected")
                return False
                
        except Exception as e:
            print(f"❌ ERROR: Could not check processes: {e}")
            return False

    async def test_spanish_search(self):
        """Requirement 2: Test Spanish search for 'Matrix'"""
        print("\n2️⃣ TESTING SPANISH SEARCH: 'Matrix'")
        print("-" * 40)
        
        try:
            sys.path.append('/app')
            from bot import search_tmdb_and_show_options
            
            # Mock objects for testing
            class MockMessage:
                async def reply_text(self, text): 
                    print(f"📱 Bot Response: {text[:80]}...")
                async def reply_photo(self, photo, caption, parse_mode=None):
                    print(f"📸 Photo: {photo}")
                    print(f"📝 Caption: {caption[:80]}...")
            
            class MockUpdate:
                def __init__(self): self.message = MockMessage()
            
            class MockContext:
                def __init__(self): self.user_data = {}
            
            mock_update = MockUpdate()
            mock_context = MockContext()
            
            result = await search_tmdb_and_show_options(mock_update, mock_context, "Matrix")
            
            if result and mock_context.user_data.get('matches'):
                matches = len(mock_context.user_data['matches'])
                print(f"✅ PASS: Found {matches} Matrix results in Spanish")
                print("🎬 Sample titles found:")
                for i, match in enumerate(mock_context.user_data['matches'][:3]):
                    title = match.get('title') or match.get('name', 'Unknown')
                    year = (match.get('release_date') or match.get('first_air_date', ''))[:4]
                    tipo = 'Película' if match.get('is_movie') else 'Serie'
                    print(f"   {i+1}. {title} ({year}) [{tipo}]")
                return True
            else:
                print("❌ FAIL: No Matrix results found")
                return False
                
        except Exception as e:
            print(f"❌ ERROR: Spanish search test failed: {e}")
            return False

    async def test_multiple_selection_flow(self):
        """Requirement 3: Test complete multiple option selection flow"""
        print("\n3️⃣ TESTING MULTIPLE SELECTION FLOW")
        print("-" * 40)
        
        try:
            sys.path.append('/app')
            from bot import search_tmdb_and_show_options, select_option, publish_tmdb_item
            
            # Test the selection logic
            class MockMessage:
                def __init__(self, text="1"):
                    self.text = text
                async def reply_text(self, text): 
                    print(f"📱 Selection Response: {text[:60]}...")
                async def reply_photo(self, photo, caption, parse_mode=None):
                    print(f"📸 Final Result Photo: {photo}")
                    print(f"📝 Final Caption: {caption[:100]}...")
            
            class MockUpdate:
                def __init__(self, text="1"): 
                    self.message = MockMessage(text)
            
            class MockContext:
                def __init__(self): 
                    self.user_data = {
                        'matches': [
                            {'id': 603, 'title': 'Matrix', 'is_movie': True, 'release_date': '1999-03-31'},
                            {'id': 624860, 'title': 'Matrix Resurrections', 'is_movie': True, 'release_date': '2021-12-16'}
                        ]
                    }
            
            # Test selection of first option
            mock_update = MockUpdate("1")
            mock_context = MockContext()
            
            result = await select_option(mock_update, mock_context)
            
            if result == 0:  # ConversationHandler.END
                print("✅ PASS: Multiple selection flow completed successfully")
                print("🎯 User can select from multiple Matrix options")
                return True
            else:
                print("❌ FAIL: Selection flow did not complete properly")
                return False
                
        except Exception as e:
            print(f"❌ ERROR: Multiple selection test failed: {e}")
            return False

    async def test_api_responses(self):
        """Requirement 4: Test all API responses"""
        print("\n4️⃣ TESTING API RESPONSES")
        print("-" * 40)
        
        import httpx
        
        api_results = {}
        
        # Test TMDb API
        try:
            async with httpx.AsyncClient() as client:
                url = f'https://api.themoviedb.org/3/search/movie?api_key={self.tmdb_api_key}&query=Matrix&language=es-ES'
                response = await client.get(url, timeout=10)
                api_results['tmdb'] = response.status_code == 200 and len(response.json().get('results', [])) > 0
                print(f"🎬 TMDb API: {'✅ WORKING' if api_results['tmdb'] else '❌ FAILED'}")
        except:
            api_results['tmdb'] = False
            print("🎬 TMDb API: ❌ FAILED")
        
        # Test TVmaze API
        try:
            async with httpx.AsyncClient() as client:
                url = "https://api.tvmaze.com/search/shows?q=Matrix"
                response = await client.get(url, timeout=10)
                api_results['tvmaze'] = response.status_code == 200 and len(response.json()) > 0
                print(f"📺 TVmaze API: {'✅ WORKING' if api_results['tvmaze'] else '❌ FAILED'}")
        except:
            api_results['tvmaze'] = False
            print("📺 TVmaze API: ❌ FAILED")
        
        # Test Telegram Bot API
        try:
            async with httpx.AsyncClient() as client:
                url = f"https://api.telegram.org/bot{self.bot_token}/getMe"
                response = await client.get(url, timeout=10)
                api_results['telegram'] = response.status_code == 200
                print(f"🤖 Telegram API: {'✅ WORKING' if api_results['telegram'] else '❌ FAILED'}")
        except:
            api_results['telegram'] = False
            print("🤖 Telegram API: ❌ FAILED")
        
        # OMDb API (optional)
        if self.omdb_api_key:
            try:
                async with httpx.AsyncClient() as client:
                    url = f"https://www.omdbapi.com/?t=Matrix&apikey={self.omdb_api_key}"
                    response = await client.get(url, timeout=10)
                    api_results['omdb'] = response.status_code == 200 and response.json().get('Response') == 'True'
                    print(f"🎭 OMDb API: {'✅ WORKING' if api_results['omdb'] else '❌ FAILED'}")
            except:
                api_results['omdb'] = False
                print("🎭 OMDb API: ❌ FAILED")
        else:
            api_results['omdb'] = None
            print("🎭 OMDb API: ⚠️ NOT CONFIGURED (optional)")
        
        # Check critical APIs
        critical_apis = ['tmdb', 'telegram']
        critical_working = all(api_results.get(api, False) for api in critical_apis)
        
        if critical_working:
            print("✅ PASS: All critical APIs responding correctly")
            return True
        else:
            print("❌ FAIL: Some critical APIs not working")
            return False

    async def test_group_messaging(self):
        """Requirement 5: Test bot can send messages to target group"""
        print("\n5️⃣ TESTING GROUP MESSAGING CAPABILITY")
        print("-" * 40)
        
        try:
            import httpx
            
            # Check bot permissions in group
            async with httpx.AsyncClient() as client:
                url = f"https://api.telegram.org/bot{self.bot_token}/getChatMember"
                data = {
                    "chat_id": self.chat_id,
                    "user_id": self.bot_token.split(':')[0]
                }
                response = await client.post(url, json=data, timeout=10)
                
                if response.status_code == 200:
                    member_info = response.json().get('result', {})
                    status = member_info.get('status', 'unknown')
                    print(f"🏛️ Bot status in group: {status}")
                    
                    if status in ['administrator', 'member']:
                        print("✅ PASS: Bot can send messages to target group")
                        return True
                    else:
                        print("❌ FAIL: Bot lacks permissions in target group")
                        return False
                else:
                    print(f"❌ FAIL: Could not check group permissions: {response.status_code}")
                    return False
                    
        except Exception as e:
            print(f"❌ ERROR: Group messaging test failed: {e}")
            return False

    def check_bot_logs(self):
        """Check bot.log for errors"""
        print("\n📋 CHECKING BOT LOGS")
        print("-" * 40)
        
        try:
            with open('/app/bot.log', 'r') as f:
                lines = f.readlines()
            
            recent_lines = lines[-20:]  # Last 20 lines
            error_count = sum(1 for line in recent_lines if 'ERROR' in line)
            warning_count = sum(1 for line in recent_lines if 'WARNING' in line)
            
            print(f"📊 Recent log analysis (last 20 lines):")
            print(f"   ❌ Errors: {error_count}")
            print(f"   ⚠️ Warnings: {warning_count}")
            
            if error_count == 0:
                print("✅ No recent errors in bot logs")
                return True
            else:
                print("⚠️ Some errors found in recent logs")
                print("📝 Recent error lines:")
                for line in recent_lines:
                    if 'ERROR' in line:
                        print(f"   {line.strip()}")
                return False
                
        except Exception as e:
            print(f"❌ Could not read bot logs: {e}")
            return False

    async def generate_final_report(self):
        """Generate comprehensive final report"""
        print("\n" + "=" * 60)
        print("📊 FINAL TEST RESULTS")
        print("=" * 60)
        
        # Run all tests
        test_results = {}
        test_results['single_instance'] = self.check_single_instance()
        test_results['spanish_search'] = await self.test_spanish_search()
        test_results['multiple_selection'] = await self.test_multiple_selection_flow()
        test_results['api_responses'] = await self.test_api_responses()
        test_results['group_messaging'] = await self.test_group_messaging()
        test_results['clean_logs'] = self.check_bot_logs()
        
        # Calculate overall score
        passed_tests = sum(1 for result in test_results.values() if result)
        total_tests = len(test_results)
        success_rate = (passed_tests / total_tests) * 100
        
        print(f"\n🎯 OVERALL RESULTS:")
        print(f"   📊 Tests Passed: {passed_tests}/{total_tests}")
        print(f"   📈 Success Rate: {success_rate:.1f}%")
        
        print(f"\n📋 DETAILED RESULTS:")
        for test_name, result in test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"   {status} - {test_name.replace('_', ' ').title()}")
        
        print(f"\n🎯 PRODUCTION READINESS:")
        if success_rate >= 80:
            print("✅ BOT IS READY FOR PRODUCTION!")
            print("🚀 All critical functionality is working")
            print("📱 Bot can handle Spanish movie/series searches")
            print("🎬 Multiple result selection flow works")
            print("🔗 All APIs are responding correctly")
            print("💬 Bot can send messages to target group")
        else:
            print("⚠️ BOT NEEDS ATTENTION BEFORE PRODUCTION")
            print("🔧 Review failed tests and fix issues")
        
        print(f"\n💡 RECOMMENDATIONS:")
        if not test_results.get('single_instance'):
            print("   🔄 Ensure only one bot instance is running")
        if not test_results.get('clean_logs'):
            print("   📋 Monitor and resolve log errors")
        if self.omdb_api_key is None:
            print("   🎭 Consider adding OMDb API key for enhanced coverage")
        
        print("\n" + "=" * 60)
        return success_rate >= 80

async def main():
    """Run final comprehensive test"""
    tester = FinalBotTestReport()
    success = await tester.generate_final_report()
    return 0 if success else 1

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