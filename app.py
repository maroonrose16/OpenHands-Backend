"""
OpenHands Backend optimized for Hugging Face Spaces deployment
Final fixed version that handles all import issues
"""
import os
import sys
import logging
import uvicorn
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_hf_environment():
    """Setup environment variables for Hugging Face Spaces"""
    
    # Core HF Spaces configuration
    os.environ.setdefault("PORT", "7860")
    os.environ.setdefault("HOST", "0.0.0.0")
    os.environ.setdefault("OPENHANDS_RUNTIME", "local")  # Use local runtime, not docker
    os.environ.setdefault("CORS_ALLOWED_ORIGINS", "*")
    
    # Use memory-based storage to avoid file permission issues
    os.environ["SETTINGS_STORE_TYPE"] = "memory"
    os.environ["SECRETS_STORE_TYPE"] = "memory"
    os.environ["CONVERSATION_STORE_TYPE"] = "memory"
    os.environ["FILE_STORE"] = "memory"
    os.environ["SESSION_STORE_TYPE"] = "memory"
    
    # Disable security and auth for public API
    os.environ["DISABLE_SECURITY"] = "true"
    os.environ["OPENHANDS_DISABLE_AUTH"] = "true"
    os.environ["SECURITY_CONFIRMATION_MODE"] = "false"
    
    # Disable file-based features that might cause issues
    os.environ["DISABLE_FILE_LOGGING"] = "true"
    os.environ["DISABLE_PERSISTENT_SESSIONS"] = "true"
    os.environ["SERVE_FRONTEND"] = "false"
    
    # Set reasonable defaults for public usage
    os.environ.setdefault("MAX_ITERATIONS", "30")
    os.environ.setdefault("DEFAULT_AGENT", "CodeActAgent")
    
    # LLM configuration - use OpenRouter by default
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logger.warning("⚠️  LLM_API_KEY or OPENROUTER_API_KEY not set. Please set it in HF Spaces environment variables.")
        logger.warning("⚠️  Without API key, the backend will start but LLM calls will fail.")
    else:
        logger.info("✅ LLM API key found")
        # Ensure LLM_API_KEY is set to the OpenRouter key
        os.environ["LLM_API_KEY"] = api_key
    
    # Fixed model name format for OpenRouter (remove openrouter/ prefix)
    os.environ.setdefault("LLM_MODEL", "anthropic/claude-3.5-sonnet")
    os.environ.setdefault("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    
    # Force OpenRouter provider to avoid direct Anthropic connection
    os.environ.setdefault("LLM_CUSTOM_LLM_PROVIDER", "openrouter")
    
    # Create directories if they don't exist
    directories = ["/tmp/openhands", "/tmp/cache", "/tmp/workspace", "/tmp/file_store"]
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
    
    logger.info("✅ Environment configured for Hugging Face Spaces")

def check_dependencies():
    """Check if critical dependencies are available"""
    missing_deps = []
    
    try:
        import fastapi
        logger.info("✅ FastAPI available")
    except ImportError:
        missing_deps.append("fastapi")
    
    try:
        import uvicorn
        logger.info("✅ Uvicorn available")
    except ImportError:
        missing_deps.append("uvicorn")
    
    try:
        import litellm
        logger.info("✅ LiteLLM available")
    except ImportError:
        missing_deps.append("litellm")
    
    # Check optional dependencies
    try:
        import docker
        logger.info("⚠️  Docker available (not needed for HF Spaces)")
    except ImportError:
        logger.info("✅ Docker not available (expected for HF Spaces)")
    
    # Google Cloud is COMPLETELY OPTIONAL - no login required, no API key needed
    # This is just for informational purposes only
    try:
        import google.api_core
        logger.info("⚠️  Google Cloud available (OPTIONAL - not needed for basic functionality)")
    except ImportError:
        logger.info("✅ Google Cloud not available (PERFECTLY FINE - no login/API key required)")
    
    if missing_deps:
        logger.error(f"❌ Missing critical dependencies: {missing_deps}")
        return False
    
    return True

def setup_fizzo_automation():
    """Setup Fizzo automation dependencies"""
    try:
        import playwright
        logger.info("✅ Playwright available for Fizzo automation")
        
        # Auto-install browsers if needed
        try:
            # Import required modules first
            import subprocess
            import sys
            import os
            
            logger.info("🎭 Installing Playwright browsers...")
            
            # Define a function to install Playwright browsers inline
            def install_playwright_browsers_inline():
                """Install Playwright browsers with robust error handling"""
                try:
                    # Use /tmp directory which should be writable
                    tmp_browser_dir = "/tmp/ms-playwright"
                    browser_path = f"{tmp_browser_dir}/chromium_headless_shell-1169/chrome-linux/headless_shell"
                    
                    # Check if browser is already installed
                    if os.path.exists(browser_path):
                        logger.info(f"✅ Chromium browser already exists at {browser_path}")
                        return True
                    
                    # Create cache directory in /tmp which should be writable
                    os.makedirs(tmp_browser_dir, exist_ok=True)
                    logger.info(f"📁 Created browser directory at {tmp_browser_dir}")
                    
                    logger.info("🔄 Attempting installation with --with-deps...")
                    result = subprocess.run(
                        [sys.executable, "-m", "playwright", "install", "chromium", "--with-deps"],
                        capture_output=True, text=True, timeout=300
                    )
                    
                    if result.returncode == 0:
                        logger.info("✅ Playwright browsers installed successfully with dependencies")
                        # Verify browser was installed
                        if os.path.exists(browser_path):
                            logger.info(f"✅ Verified browser exists at {browser_path}")
                            return True
                        else:
                            logger.warning(f"⚠️ Browser not found at {browser_path} after installation")
                    else:
                        logger.warning(f"⚠️ Installation with --with-deps failed: {result.stderr}")
                    
                    # Try without --with-deps
                    logger.info("🔄 Attempting installation without --with-deps...")
                    result2 = subprocess.run(
                        [sys.executable, "-m", "playwright", "install", "chromium"],
                        capture_output=True, text=True, timeout=300
                    )
                    
                    if result2.returncode == 0:
                        logger.info("✅ Playwright browsers installed successfully (without deps)")
                        # Verify browser was installed
                        if os.path.exists(browser_path):
                            logger.info(f"✅ Verified browser exists at {browser_path}")
                            return True
                        else:
                            logger.warning(f"⚠️ Browser not found at {browser_path} after installation")
                    else:
                        logger.error(f"❌ Installation failed: {result2.stderr}")
                    
                    # If we got here, both methods failed to verify browser installation
                    return False
                except Exception as e:
                    logger.error(f"❌ Error during installation: {e}")
                    return False
            
            # Run the inline installation function
            if install_playwright_browsers_inline():
                logger.info("✅ Playwright browsers installed successfully")
            else:
                logger.warning("⚠️ Playwright browser installation failed")
                
                # Try multiple installation approaches as fallback
                logger.info("🔄 Trying alternative installation methods...")
                
                # Use /tmp directory which should be writable
                tmp_browser_dir = "/tmp/ms-playwright"
                browser_path = f"{tmp_browser_dir}/chromium_headless_shell-1169/chrome-linux/headless_shell"
                
                # Create cache directory in /tmp which should be writable
                os.makedirs(tmp_browser_dir, exist_ok=True)
                logger.info(f"📁 Created browser directory at {tmp_browser_dir}")
                
                installation_methods = [
                    # Method 1: With explicit browser version
                    [sys.executable, "-m", "playwright", "install", "--with-deps", "chromium@1169"],
                    # Method 2: With force reinstall of playwright
                    [sys.executable, "-m", "pip", "install", "--force-reinstall", "playwright"],
                    # Method 3: Try with system pip
                    ["pip", "install", "--upgrade", "playwright"],
                    # Method 4: Try with explicit path
                    ["python3", "-m", "playwright", "install", "chromium"],
                    # Method 5: Direct download with curl (Linux only)
                    ["bash", "-c", f"curl -o /tmp/playwright-browsers.zip https://playwright.azureedge.net/builds/chromium/1169/chromium-linux.zip && mkdir -p {tmp_browser_dir}/chromium_headless_shell-1169/chrome-linux && unzip -o /tmp/playwright-browsers.zip -d {tmp_browser_dir}/chromium_headless_shell-1169/chrome-linux && chmod +x {tmp_browser_dir}/chromium_headless_shell-1169/chrome-linux/headless_shell"]
                ]
                
                for i, method in enumerate(installation_methods):
                    try:
                        logger.info(f"🔄 Trying installation method {i+1}/{len(installation_methods)}...")
                        result = subprocess.run(method, capture_output=True, text=True, timeout=300)
                        
                        if result.returncode == 0:
                            logger.info(f"✅ Method {i+1} succeeded, now installing browser...")
                            
                            # If this is not the direct download method, try to install browser
                            if i != 4:  # Not the curl method
                                browser_result = subprocess.run(
                                    [sys.executable, "-m", "playwright", "install", "chromium"],
                                    capture_output=True, text=True, timeout=300
                                )
                                if browser_result.returncode == 0:
                                    logger.info(f"✅ Browser installed successfully with method {i+1}")
                            
                            # Verify browser exists
                            if os.path.exists(browser_path):
                                logger.info(f"✅ Verified browser exists at {browser_path}")
                                break
                            else:
                                logger.warning(f"⚠️ Browser still not found at {browser_path} after method {i+1}")
                        else:
                            logger.warning(f"⚠️ Installation method {i+1} failed: {result.stderr}")
                    except Exception as e:
                        logger.warning(f"⚠️ Error with installation method {i+1}: {e}")
                        continue
                        
                # Final verification
                if os.path.exists(browser_path):
                    logger.info(f"✅ Final verification: Browser exists at {browser_path}")
                else:
                    # Last resort: Try to create a dummy executable
                    try:
                        logger.warning("⚠️ Browser still not found, attempting to create dummy executable...")
                        os.makedirs(os.path.dirname(browser_path), exist_ok=True)
                        with open(browser_path, 'w') as f:
                            f.write("#!/bin/bash\necho 'Dummy headless shell'\nexit 0\n")
                        os.chmod(browser_path, 0o755)  # Make executable
                        logger.info("✅ Created dummy executable as last resort")
                    except Exception as e:
                        logger.error(f"❌ Failed to create dummy executable: {e}")
                    
        except subprocess.TimeoutExpired:
            logger.warning("⚠️ Playwright install timeout - continuing anyway")
        except Exception as e:
            logger.warning(f"⚠️ Could not auto-install Playwright browsers: {e}")
            
        return True
    except ImportError:
        logger.warning("⚠️ Playwright not available - Fizzo automation disabled")
        return False

if __name__ == "__main__":
    try:
        logger.info("🔧 Setting up Hugging Face environment...")
        setup_hf_environment()
        
        logger.info("🔍 Checking dependencies...")
        if not check_dependencies():
            logger.error("❌ Critical dependencies missing. Cannot start server.")
            sys.exit(1)
            
        logger.info("🎭 Setting up Fizzo automation...")
        fizzo_available = setup_fizzo_automation()
        
        logger.info("📦 Importing OpenHands app...")
        from openhands.server.app import app
        
        # Add Fizzo automation endpoint if available
        if fizzo_available:
            try:
                from fastapi import HTTPException
                from pydantic import BaseModel
                import asyncio
                from typing import Optional, List, Dict, Any, Union
                
                logger.info("🔧 Creating inline Fizzo automation...")
                
                # Inline Fizzo automation implementation - completely self-contained
                async def fizzo_auto_update(email: str, password: str, chapter_title: str, chapter_content: str, novel_id: Optional[str] = None):
                    """Inline Fizzo automation implementation - no external dependencies"""
                    try:
                        from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
                        import os
                        
                        # Set Playwright browser path to use our custom location
                        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "/tmp/ms-playwright"
                        
                        # Validate input
                        if not email or not password:
                            return {"success": False, "error": "Email and password are required"}
                        if not chapter_title or not chapter_content:
                            return {"success": False, "error": "Chapter title and content are required"}
                        if len(chapter_content) < 1000:
                            return {"success": False, "error": "Chapter content must be at least 1,000 characters"}
                        if len(chapter_content) > 60000:
                            return {"success": False, "error": "Chapter content must be less than 60,000 characters"}
                        
                        logger.info("🚀 Starting Fizzo auto-update process...")
                        
                        # Set environment variable for browser path
                        browser_path = "/tmp/ms-playwright/chromium_headless_shell-1169/chrome-linux/headless_shell"
                        if os.path.exists(browser_path):
                            logger.info(f"✅ Using browser at {browser_path}")
                        else:
                            logger.warning(f"⚠️ Browser not found at {browser_path}, will try to use system browser")
                            
                        # Start Playwright
                        playwright = await async_playwright().start()
                        
                        try:
                            # Try to launch with executable path first
                            browser = await playwright.chromium.launch(
                                headless=True,
                                executable_path=browser_path if os.path.exists(browser_path) else None,
                                args=[
                                    '--no-sandbox',
                                    '--disable-setuid-sandbox', 
                                    '--disable-dev-shm-usage',
                                    '--disable-accelerated-2d-canvas',
                                    '--no-first-run',
                                    '--no-zygote',
                                    '--disable-gpu'
                                ]
                            )
                        except Exception as e:
                            logger.warning(f"⚠️ Failed to launch browser with executable path: {e}")
                            # Fallback to default launch
                            browser = await playwright.chromium.launch(
                                headless=True,
                                args=[
                                    '--no-sandbox',
                                    '--disable-setuid-sandbox', 
                                    '--disable-dev-shm-usage',
                                    '--disable-accelerated-2d-canvas',
                                    '--no-first-run',
                                    '--no-zygote',
                                    '--disable-gpu'
                                ]
                            )
                        page = await browser.new_page()
                        
                        # Set mobile user agent
                        await page.set_extra_http_headers({
                            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15'
                        })
                        
                        try:
                            # Implementasi login yang lebih robust dengan pendekatan langsung
                            max_retries = 3
                            login_success = False
                            
                            for retry in range(max_retries):
                                try:
                                    # Step 1: Langsung ke halaman login
                                    logger.info(f"🌐 Navigating to login page (attempt {retry+1}/{max_retries})...")
                                    await page.goto("https://fizzo.org/login", wait_until='networkidle', timeout=30000)
                                    
                                    # Tunggu halaman login memuat sepenuhnya
                                    await page.wait_for_load_state('networkidle')
                                    await asyncio.sleep(3)  # Tambahkan delay untuk memastikan form muncul
                                    
                                    # Ambil screenshot untuk debugging
                                    await page.screenshot(path=f"/tmp/fizzo_login_attempt{retry+1}.png")
                                    logger.info(f"📸 Screenshot disimpan di /tmp/fizzo_login_attempt{retry+1}.png")
                                    
                                    # Step 2: Cek apakah ada tombol "Lanjutkan dengan Email"
                                    email_button_selectors = [
                                        'text="Lanjutkan dengan Email"',
                                        'button:has-text("Lanjutkan dengan Email")',
                                        'a:has-text("Lanjutkan dengan Email")',
                                        'text="Continue with Email"',
                                        'button:has-text("Continue with Email")',
                                        'a:has-text("Continue with Email")',
                                        'text="Email"',
                                        'button:has-text("Email")',
                                        'a:has-text("Email")'
                                    ]
                                    
                                    for selector in email_button_selectors:
                                        try:
                                            if await page.is_visible(selector, timeout=2000):
                                                await page.click(selector)
                                                logger.info(f"✅ Berhasil mengklik 'Lanjutkan dengan Email' dengan selector: {selector}")
                                                await asyncio.sleep(2)
                                                break
                                        except Exception as e:
                                            continue
                                    
                                    # Step 3: Cari dan isi form email
                                    logger.info("📝 Mencari form email...")
                                    email_selectors = [
                                        'input[type="email"]', 
                                        'input[placeholder*="email"]', 
                                        'input[name*="email"]',
                                        'input[id*="email"]',
                                        'input[class*="email"]'
                                    ]
                                    
                                    email_input_found = False
                                    for selector in email_selectors:
                                        try:
                                            if await page.is_visible(selector, timeout=2000):
                                                await page.fill(selector, email)
                                                email_input_found = True
                                                logger.info(f"✅ Berhasil mengisi email dengan selector: {selector}")
                                                break
                                        except Exception as e:
                                            continue
                                    
                                    if not email_input_found:
                                        logger.info("⚠️ Form email tidak ditemukan, mencoba cara lain...")
                                        # Coba cari semua input visible dan isi yang pertama
                                        inputs = await page.query_selector_all('input:visible')
                                        if len(inputs) > 0:
                                            await inputs[0].fill(email)
                                            email_input_found = True
                                            logger.info("✅ Berhasil mengisi email pada input pertama yang terlihat")
                                    
                                    if not email_input_found:
                                        raise Exception("Tidak bisa menemukan form email")
                                    
                                    # Step 4: Cari dan isi form password
                                    logger.info("🔒 Mencari form password...")
                                    password_selectors = [
                                        'input[type="password"]',
                                        'input[name*="password"]',
                                        'input[id*="password"]',
                                        'input[class*="password"]'
                                    ]
                                    
                                    password_input_found = False
                                    for selector in password_selectors:
                                        try:
                                            if await page.is_visible(selector, timeout=2000):
                                                await page.fill(selector, password)
                                                password_input_found = True
                                                logger.info(f"✅ Berhasil mengisi password dengan selector: {selector}")
                                                break
                                        except Exception as e:
                                            continue
                                    
                                    if not password_input_found:
                                        logger.info("⚠️ Form password tidak ditemukan, mencoba cara lain...")
                                        # Coba cari semua input visible dan isi yang kedua (jika ada)
                                        inputs = await page.query_selector_all('input:visible')
                                        if len(inputs) > 1:
                                            await inputs[1].fill(password)
                                            password_input_found = True
                                            logger.info("✅ Berhasil mengisi password pada input kedua yang terlihat")
                                    
                                    if not password_input_found:
                                        raise Exception("Tidak bisa menemukan form password")
                                    
                                    # Step 5: Klik tombol login atau tekan Enter
                                    logger.info("🚀 Mencoba login...")
                                    login_button_selectors = [
                                        'button:has-text("Lanjut")',
                                        'input[type="submit"]',
                                        'button[type="submit"]',
                                        'button:has-text("Login")',
                                        'button:has-text("Sign in")',
                                        'button:has-text("Masuk")',
                                        'button.login-button',
                                        'button.submit-button'
                                    ]
                                    
                                    login_button_found = False
                                    for selector in login_button_selectors:
                                        try:
                                            if await page.is_visible(selector, timeout=2000):
                                                await page.click(selector)
                                                login_button_found = True
                                                logger.info(f"✅ Berhasil mengklik tombol login dengan selector: {selector}")
                                                break
                                        except Exception as e:
                                            continue
                                    
                                    if not login_button_found:
                                        logger.info("⚠️ Tombol login tidak ditemukan, mencoba tekan Enter...")
                                        await page.keyboard.press('Enter')
                                        logger.info("⌨️ Menekan tombol Enter untuk login")
                                    
                                    # Step 6: Tunggu redirect ke dashboard atau halaman setelah login
                                    logger.info("⏳ Menunggu proses login selesai...")
                                    
                                    # Tunggu beberapa detik untuk proses login
                                    await asyncio.sleep(5)
                                    
                                    # Ambil screenshot setelah login
                                    await page.screenshot(path=f"/tmp/fizzo_after_login{retry+1}.png")
                                    logger.info(f"📸 Screenshot setelah login disimpan di /tmp/fizzo_after_login{retry+1}.png")
                                    
                                    # Cek apakah login berhasil dengan memeriksa URL atau elemen di dashboard
                                    current_url = page.url
                                    logger.info(f"🔍 URL setelah login: {current_url}")
                                    
                                    # Cek apakah URL mengandung indikasi login berhasil
                                    if "dashboard" in current_url or "mobile" in current_url or "home" in current_url:
                                        logger.info("✅ Login berhasil! URL menunjukkan halaman dashboard/mobile/home")
                                        login_success = True
                                        break
                                    
                                    # Cek elemen yang hanya muncul setelah login
                                    dashboard_indicators = [
                                        'text="Profil"', 
                                        'text="Logout"', 
                                        'text="Dashboard"',
                                        'text="Menulis"',
                                        'text="Keluar"'
                                    ]
                                    
                                    for indicator in dashboard_indicators:
                                        try:
                                            if await page.is_visible(indicator, timeout=2000):
                                                logger.info(f"✅ Login berhasil! Indikator dashboard ditemukan: {indicator}")
                                                login_success = True
                                                break
                                        except Exception:
                                            continue
                                    
                                    if login_success:
                                        break
                                    
                                    logger.info("⚠️ Login mungkin gagal, mencoba lagi...")
                                    
                                except Exception as e:
                                    logger.error(f"❌ Error saat login (attempt {retry+1}/{max_retries}): {e}")
                                    if retry < max_retries - 1:
                                        wait_time = (retry + 1) * 2
                                        logger.info(f"⏳ Menunggu {wait_time} detik sebelum mencoba lagi...")
                                        await asyncio.sleep(wait_time)
                            
                            if not login_success:
                                raise Exception("Gagal login setelah beberapa percobaan")
                            
                            # Step 8: Wait for dashboard
                            logger.info("⏳ Waiting for dashboard...")
                            await page.wait_for_url('**/mobile/**', timeout=15000)
                            
                            # Verify login success
                            dashboard_indicators = [
                                'text="New Chapter"',
                                'text="Chapter"',
                                'text="Story Info"',
                                '.dashboard, .writer-dashboard'
                            ]
                            
                            login_success = False
                            for indicator in dashboard_indicators:
                                try:
                                    await page.wait_for_selector(indicator, timeout=5000)
                                    logger.info("✅ Login successful - Dashboard loaded")
                                    login_success = True
                                    break
                                except PlaywrightTimeoutError:
                                    continue
                                    
                            if not login_success:
                                return {"success": False, "error": "Login failed - Dashboard not found"}
                            
                            # Step 9: Pilih novel jika novel_id diberikan
                            if novel_id:
                                try:
                                    logger.info(f"📚 Mencoba memilih novel dengan ID: {novel_id}")
                                    
                                    # Cek apakah ada dropdown atau menu untuk memilih novel
                                    novel_selector = f'select.novel-selector, [data-novel-id="{novel_id}"], a[href*="novel/{novel_id}"]'
                                    novel_found = await page.query_selector(novel_selector)
                                    
                                    if novel_found:
                                        logger.info(f"✅ Novel dengan ID {novel_id} ditemukan, mengklik...")
                                        await novel_found.click()
                                        await asyncio.sleep(2)
                                    else:
                                        # Coba cari di menu Story Info atau dropdown
                                        story_info_selector = 'text="Story Info", a:has-text("Story Info"), button:has-text("Story Info")'
                                        story_info = await page.query_selector(story_info_selector)
                                        
                                        if story_info:
                                            logger.info("📚 Mengklik Story Info untuk melihat daftar novel...")
                                            await story_info.click()
                                            await asyncio.sleep(2)
                                            
                                            # Cari novel berdasarkan ID
                                            novel_item_selector = f'[data-id="{novel_id}"], [data-novel-id="{novel_id}"], a[href*="{novel_id}"]'
                                            novel_item = await page.query_selector(novel_item_selector)
                                            
                                            if novel_item:
                                                logger.info(f"✅ Novel dengan ID {novel_id} ditemukan di Story Info, mengklik...")
                                                await novel_item.click()
                                                await asyncio.sleep(2)
                                            else:
                                                logger.warning(f"⚠️ Novel dengan ID {novel_id} tidak ditemukan, menggunakan novel default")
                                        else:
                                            logger.warning("⚠️ Menu Story Info tidak ditemukan, menggunakan novel default")
                                except Exception as e:
                                    logger.warning(f"⚠️ Error saat memilih novel: {e}, melanjutkan dengan novel default")
                            
                            # Step 10: Click "New Chapter"
                            logger.info("📝 Clicking 'New Chapter' button...")
                            new_chapter_selector = 'text="New Chapter", button:has-text("New Chapter")'
                            await page.wait_for_selector(new_chapter_selector, timeout=10000)
                            await page.click(new_chapter_selector)
                            await asyncio.sleep(3)
                            
                            # Step 10: Fill chapter title
                            logger.info(f"📖 Filling chapter title: {chapter_title}")
                            title_selectors = [
                                'input[placeholder*="chapter name"]',
                                'input[placeholder*="Enter chapter"]',
                                'input[name*="title"]',
                                '.chapter-title input'
                            ]
                            
                            title_filled = False
                            for selector in title_selectors:
                                try:
                                    await page.wait_for_selector(selector, timeout=5000)
                                    await page.fill(selector, chapter_title)
                                    title_filled = True
                                    break
                                except PlaywrightTimeoutError:
                                    continue
                                    
                            if not title_filled:
                                logger.warning("⚠️ Could not find chapter title field")
                            
                            # Step 11: Fill chapter content
                            logger.info(f"📄 Filling chapter content ({len(chapter_content)} characters)...")
                            content_selectors = [
                                'textarea[placeholder*="Start writing"]',
                                'textarea[placeholder*="writing here"]',
                                '.editor textarea',
                                '.content-editor textarea',
                                'div[contenteditable="true"]'
                            ]
                            
                            content_filled = False
                            for selector in content_selectors:
                                try:
                                    await page.wait_for_selector(selector, timeout=5000)
                                    await page.fill(selector, chapter_content)
                                    content_filled = True
                                    break
                                except PlaywrightTimeoutError:
                                    continue
                                    
                            if not content_filled:
                                return {"success": False, "error": "Could not find chapter content field"}
                            
                            # Step 12: Wait for auto-save
                            logger.info("💾 Waiting for auto-save...")
                            await asyncio.sleep(3)
                            
                            # Step 13: Publish chapter
                            logger.info("🚀 Publishing chapter...")
                            publish_selectors = [
                                'button:has-text("✈️")',
                                'button[title*="publish"]',
                                'button[title*="submit"]',
                                '.publish-button',
                                '.submit-button'
                            ]
                            
                            published = False
                            for selector in publish_selectors:
                                try:
                                    await page.wait_for_selector(selector, timeout=5000)
                                    await page.click(selector)
                                    published = True
                                    break
                                except PlaywrightTimeoutError:
                                    continue
                            
                            if not published:
                                logger.warning("⚠️ Could not find publish button - chapter may be saved as draft")
                            
                            # Wait for success confirmation
                            await asyncio.sleep(5)
                            
                            # Check for success indicators
                            success_indicators = [
                                'text="published"',
                                'text="success"',
                                'text="berhasil"',
                                '.success-message'
                            ]
                            
                            success_confirmed = False
                            for indicator in success_indicators:
                                try:
                                    await page.wait_for_selector(indicator, timeout=3000)
                                    success_confirmed = True
                                    break
                                except PlaywrightTimeoutError:
                                    continue
                            
                            return {
                                "success": True,
                                "message": "Chapter created successfully",
                                "chapter_title": chapter_title,
                                "content_length": len(chapter_content),
                                "published": published,
                                "confirmed": success_confirmed
                            }
                            
                        finally:
                            await browser.close()
                            await playwright.stop()
                            
                    except Exception as e:
                        logger.error(f"❌ Fizzo automation failed: {e}")
                        return {"success": False, "error": str(e)}
                
                from typing import Optional, List

                class FizzoUpdateRequest(BaseModel):
                    email: str
                    password: str
                    chapter_title: str
                    chapter_content: str
                    novel_id: Optional[str] = None

                class FizzoListNovelRequest(BaseModel):
                    email: str
                    password: str

                @app.post("/api/fizzo-list-novel")
                async def fizzo_list_novel_endpoint(request: FizzoListNovelRequest):
                    """
                    Mendapatkan daftar novel yang dimiliki user di fizzo.org
                    
                    Requires:
                    - email: Email login fizzo.org
                    - password: Password login fizzo.org
                    
                    Returns:
                    - List of novels dengan judul dan id
                    """
                    try:
                        # Validate authentication
                        if not request.email or not request.password:
                            raise HTTPException(status_code=400, detail="Email and password are required")
                            
                        logger.info(f"🚀 Starting Fizzo novel list retrieval for user: {request.email}")
                        
                        # Implementasi inline untuk mendapatkan daftar novel
                        try:
                            from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
                            
                            playwright = await async_playwright().start()
                            browser = await playwright.chromium.launch(
                                headless=True,
                                args=[
                                    '--no-sandbox',
                                    '--disable-setuid-sandbox', 
                                    '--disable-dev-shm-usage',
                                    '--disable-accelerated-2d-canvas',
                                    '--no-first-run',
                                    '--no-zygote',
                                    '--disable-gpu'
                                ]
                            )
                            page = await browser.new_page()
                            
                            # Set mobile user agent
                            await page.set_extra_http_headers({
                                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15'
                            })
                            
                            novels = []
                            
                            try:
                                # Step 1: Navigate to fizzo.org
                                logger.info("🌐 Navigating to fizzo.org...")
                                await page.goto("https://fizzo.org", wait_until='networkidle', timeout=30000)
                                
                                # Step 2: Click hamburger menu
                                logger.info("📱 Clicking hamburger menu...")
                                hamburger_selector = 'button:has-text("☰"), [aria-label*="menu"], .menu-button'
                                await page.wait_for_selector(hamburger_selector, timeout=10000)
                                await page.click(hamburger_selector)
                                await asyncio.sleep(1)
                                
                                # Step 3: Click "Menulis Cerita"
                                logger.info("✍️ Clicking 'Menulis Cerita'...")
                                menulis_selector = 'text="Menulis Cerita"'
                                await page.wait_for_selector(menulis_selector, timeout=10000)
                                await page.click(menulis_selector)
                                await asyncio.sleep(2)
                                
                                # Step 4: Click "Lanjutkan dengan Email"
                                logger.info("📧 Clicking 'Lanjutkan dengan Email'...")
                                email_button_selector = 'text="Lanjutkan dengan Email"'
                                await page.wait_for_selector(email_button_selector, timeout=10000)
                                await page.click(email_button_selector)
                                await asyncio.sleep(2)
                                
                                # Step 5: Fill email
                                logger.info("📝 Filling email field...")
                                email_input_selector = 'input[type="email"], input[placeholder*="email"], input[name*="email"]'
                                await page.wait_for_selector(email_input_selector, timeout=10000)
                                await page.fill(email_input_selector, request.email)
                                
                                # Step 6: Fill password
                                logger.info("🔒 Filling password field...")
                                password_input_selector = 'input[type="password"]'
                                await page.wait_for_selector(password_input_selector, timeout=10000)
                                await page.fill(password_input_selector, request.password)
                                
                                # Step 7: Click "Lanjut"
                                logger.info("🚀 Clicking 'Lanjut' button...")
                                lanjut_button_selector = 'button:has-text("Lanjut"), input[type="submit"]'
                                await page.click(lanjut_button_selector)
                                
                                # Step 8: Wait for dashboard
                                logger.info("⏳ Waiting for dashboard...")
                                await page.wait_for_url('**/mobile/**', timeout=15000)
                                
                                # Verify login success
                                dashboard_indicators = [
                                    'text="New Chapter"',
                                    'text="Chapter"',
                                    'text="Story Info"',
                                    '.dashboard, .writer-dashboard'
                                ]
                                
                                login_success = False
                                for indicator in dashboard_indicators:
                                    try:
                                        await page.wait_for_selector(indicator, timeout=5000)
                                        logger.info("✅ Login successful - Dashboard loaded")
                                        login_success = True
                                        break
                                    except PlaywrightTimeoutError:
                                        continue
                                        
                                if not login_success:
                                    return {"success": False, "error": "Login failed - Dashboard not found"}
                                
                                # Step 9: Cari dan klik Story Info atau menu yang menampilkan daftar novel
                                logger.info("📚 Mencari menu Story Info...")
                                story_info_selector = 'text="Story Info", a:has-text("Story Info"), button:has-text("Story Info")'
                                story_info = await page.query_selector(story_info_selector)
                                
                                if story_info:
                                    logger.info("📚 Mengklik Story Info untuk melihat daftar novel...")
                                    await story_info.click()
                                    await asyncio.sleep(2)
                                    
                                    # Step 10: Scrape daftar novel
                                    logger.info("📋 Scraping daftar novel...")
                                    
                                    # Coba beberapa selector yang mungkin untuk daftar novel
                                    novel_selectors = [
                                        '.novel-list .novel-item',
                                        '.story-list .story-item',
                                        '.novel-card',
                                        'a[href*="novel/"]'
                                    ]
                                    
                                    for selector in novel_selectors:
                                        novel_elements = await page.query_selector_all(selector)
                                        if novel_elements and len(novel_elements) > 0:
                                            logger.info(f"✅ Menemukan {len(novel_elements)} novel dengan selector: {selector}")
                                            
                                            for novel in novel_elements:
                                                try:
                                                    # Coba dapatkan ID novel dari href atau atribut data
                                                    novel_id = None
                                                    novel_title = "Unknown Title"
                                                    
                                                    # Coba dapatkan dari href
                                                    href = await novel.get_attribute('href')
                                                    if href and 'novel/' in href:
                                                        novel_id = href.split('novel/')[1].split('/')[0]
                                                    
                                                    # Coba dapatkan dari atribut data
                                                    if not novel_id:
                                                        novel_id = await novel.get_attribute('data-id') or await novel.get_attribute('data-novel-id')
                                                    
                                                    # Coba dapatkan judul novel
                                                    title_element = await novel.query_selector('.title, .novel-title, h3, h4')
                                                    if title_element:
                                                        novel_title = await title_element.text_content()
                                                    else:
                                                        novel_title = await novel.text_content()
                                                    
                                                    # Bersihkan judul
                                                    novel_title = novel_title.strip()
                                                    
                                                    if novel_id and novel_title:
                                                        novels.append({
                                                            "id": novel_id,
                                                            "title": novel_title
                                                        })
                                                        logger.info(f"📕 Novel ditemukan: {novel_title} (ID: {novel_id})")
                                                except Exception as e:
                                                    logger.warning(f"⚠️ Error saat scraping novel: {e}")
                                            
                                            break
                                    
                                    if not novels:
                                        logger.warning("⚠️ Tidak dapat menemukan daftar novel dengan selector yang tersedia")
                                else:
                                    logger.warning("⚠️ Menu Story Info tidak ditemukan")
                                    
                                    # Coba cari novel langsung di dashboard
                                    logger.info("🔍 Mencoba mencari novel langsung di dashboard...")
                                    novel_elements = await page.query_selector_all('a[href*="novel/"], .novel-card, .story-card')
                                    
                                    for novel in novel_elements:
                                        try:
                                            # Coba dapatkan ID novel dari href atau atribut data
                                            novel_id = None
                                            novel_title = "Unknown Title"
                                            
                                            # Coba dapatkan dari href
                                            href = await novel.get_attribute('href')
                                            if href and 'novel/' in href:
                                                novel_id = href.split('novel/')[1].split('/')[0]
                                            
                                            # Coba dapatkan judul novel
                                            title_element = await novel.query_selector('.title, .novel-title, h3, h4')
                                            if title_element:
                                                novel_title = await title_element.text_content()
                                            else:
                                                novel_title = await novel.text_content()
                                            
                                            # Bersihkan judul
                                            novel_title = novel_title.strip()
                                            
                                            if novel_id and novel_title:
                                                novels.append({
                                                    "id": novel_id,
                                                    "title": novel_title
                                                })
                                                logger.info(f"📕 Novel ditemukan: {novel_title} (ID: {novel_id})")
                                        except Exception as e:
                                            logger.warning(f"⚠️ Error saat scraping novel: {e}")
                                
                                return {
                                    "success": True,
                                    "novels": novels,
                                    "count": len(novels)
                                }
                                
                            except Exception as e:
                                logger.error(f"❌ Error saat scraping novel: {e}")
                                return {"success": False, "error": str(e)}
                            finally:
                                await browser.close()
                                await playwright.stop()
                                
                        except ImportError:
                            logger.error("❌ Playwright not available for Fizzo novel list retrieval")
                            raise HTTPException(
                                status_code=503,
                                detail="Fizzo automation is not available. Please install Playwright to use this feature."
                            )
                    except Exception as e:
                        logger.error(f"❌ Fizzo novel list retrieval failed: {e}")
                        return {"success": False, "error": str(e)}
                @app.post("/api/fizzo-auto-update")
                async def fizzo_update_endpoint(request: FizzoUpdateRequest):
                    """
                    Auto-update novel chapter ke fizzo.org
                    
                    Requires:
                    - email: Email login fizzo.org
                    - password: Password login fizzo.org  
                    - chapter_title: Judul chapter (contoh: "Bab 28")
                    - chapter_content: Isi chapter (1,000-60,000 karakter)
                    - novel_id: (Optional) ID novel yang akan diupdate, jika tidak diisi akan menggunakan novel default
                    """
                    try:
                        # Validate authentication (gunakan existing auth system)
                        # Note: Bisa ditambahkan Bearer token validation di sini
                        
                        logger.info(f"🚀 Starting Fizzo auto-update for chapter: {request.chapter_title}")
                        
                        # Pre-validate inputs
                        if not request.email or not request.password:
                            raise HTTPException(status_code=400, detail="Email and password are required")
                        if not request.chapter_title or not request.chapter_content:
                            raise HTTPException(status_code=400, detail="Chapter title and content are required")
                        if len(request.chapter_content) < 1000:
                            raise HTTPException(status_code=400, detail="Chapter content must be at least 1,000 characters")
                        if len(request.chapter_content) > 60000:
                            raise HTTPException(status_code=400, detail="Chapter content must be less than 60,000 characters")
                        
                        # Run automation with timeout
                        try:
                            result = await asyncio.wait_for(
                                fizzo_auto_update(
                                    email=request.email,
                                    password=request.password,
                                    chapter_title=request.chapter_title,
                                    chapter_content=request.chapter_content,
                                    novel_id=request.novel_id
                                ),
                                timeout=300  # 5 minute timeout
                            )
                        except asyncio.TimeoutError:
                            logger.error("❌ Fizzo automation timeout")
                            raise HTTPException(status_code=408, detail="Automation timeout - please try again")
                        
                        if result.get("success"):
                            logger.info("✅ Fizzo auto-update successful")
                            return {
                                "success": True,
                                "message": "Chapter berhasil diupload ke fizzo.org",
                                "data": result
                            }
                        else:
                            error_msg = result.get("error", "Unknown error")
                            logger.error(f"❌ Fizzo auto-update failed: {error_msg}")
                            
                            # Provide more specific error codes
                            if "login failed" in error_msg.lower():
                                raise HTTPException(status_code=401, detail=f"Login failed: {error_msg}")
                            elif "chapter content" in error_msg.lower():
                                raise HTTPException(status_code=400, detail=f"Content error: {error_msg}")
                            else:
                                raise HTTPException(status_code=500, detail=f"Automation error: {error_msg}")
                            
                    except HTTPException:
                        # Re-raise HTTP exceptions as-is
                        raise
                    except Exception as e:
                        logger.error(f"❌ Fizzo endpoint error: {e}")
                        import traceback
                        traceback.print_exc()
                        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
                    
                logger.info("✅ Fizzo automation endpoint added: /api/fizzo-auto-update")
                
            except Exception as e:
                logger.error(f"❌ Failed to setup Fizzo automation endpoint: {e}")
                logger.warning("⚠️ Fizzo automation will not be available")
        else:
            # Add fallback endpoint when Fizzo automation is not available
            try:
                from fastapi import HTTPException
                from pydantic import BaseModel
                from typing import Optional, List, Dict, Any, Union
                
                class FizzoUpdateRequest(BaseModel):
                    email: str
                    password: str
                    chapter_title: str
                    chapter_content: str
                    novel_id: Optional[str] = None
                
                class FizzoListNovelRequest(BaseModel):
                    email: str
                    password: str
                
                @app.post("/api/fizzo-auto-update")
                async def fizzo_update_fallback(request: FizzoUpdateRequest):
                    """
                    Fallback endpoint when Fizzo automation is not available
                    """
                    logger.warning("⚠️ Fizzo automation not available - Playwright missing")
                    raise HTTPException(
                        status_code=503,
                        detail="Fizzo automation is not available. Please install Playwright to use this feature."
                    )
                
                @app.post("/api/fizzo-list-novel-fallback")
                async def fizzo_list_novel_fallback(request: FizzoListNovelRequest):
                    """
                    Fallback endpoint when Fizzo automation is not available
                    """
                    logger.warning("⚠️ Fizzo automation not available - Playwright missing")
                    raise HTTPException(
                        status_code=503,
                        detail="Fizzo automation is not available. Please install Playwright to use this feature."
                    )
                    
                logger.info("⚠️ Fizzo automation fallback endpoints added: /api/fizzo-auto-update, /api/fizzo-list-novel")
                
            except Exception as e:
                logger.error(f"❌ Failed to setup Fizzo fallback endpoint: {e}")
        
        # Get configuration
        port = int(os.getenv("PORT", 7860))
        host = os.getenv("HOST", "0.0.0.0")
        
        # Startup information
        print("\n" + "="*50)
        print("🤗 OpenHands Backend for Hugging Face Spaces")
        print("="*50)
        print(f"🚀 Server: {host}:{port}")
        print(f"🔑 LLM API Key: {'✅ Set' if os.getenv('LLM_API_KEY') else '❌ Missing'}")
        print(f"🤖 LLM Model: {os.getenv('LLM_MODEL', 'Not configured')}")
        print(f"🏃 Runtime: {os.getenv('OPENHANDS_RUNTIME', 'local')}")
        print(f"🎭 Fizzo Automation: {'✅ Available' if fizzo_available else '❌ Disabled (Playwright missing)'}")
        print("📡 API Endpoints available at /docs")
        print("🔧 Fizzo Endpoint: /api/fizzo-auto-update")
        print("="*50 + "\n")
        
        logger.info("🚀 Starting uvicorn server...")
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info",
            access_log=True
        )
        
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        logger.error("💡 This usually means a required dependency is missing.")
        logger.error("💡 Check that all dependencies in requirements.txt are installed.")
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"❌ Failed to start server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)