"""
Fizzo.org Utility Functions
Fungsi-fungsi untuk scraping dan otomatisasi fizzo.org
"""
import asyncio
import logging
from typing import Dict, Any, Optional, List, Union

logger = logging.getLogger(__name__)

async def install_playwright_if_needed():
    """
    Menginstall Playwright dan browser jika belum terinstall
    """
    try:
        import playwright
        logger.info("✅ Playwright sudah terinstall")
        
        # Coba install browser jika belum ada
        try:
            import subprocess
            import sys
            logger.info("🎭 Menginstall browser Playwright...")
            
            # Coba install dengan --with-deps
            result = subprocess.run([
                sys.executable, "-m", "playwright", "install", "chromium", "--with-deps"
            ], capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                logger.info("✅ Browser Playwright berhasil diinstall")
                return True
            else:
                logger.warning(f"⚠️ Gagal install browser dengan --with-deps: {result.stderr}")
                
                # Coba tanpa --with-deps
                result2 = subprocess.run([
                    sys.executable, "-m", "playwright", "install", "chromium"
                ], capture_output=True, text=True, timeout=300)
                
                if result2.returncode == 0:
                    logger.info("✅ Browser Playwright berhasil diinstall (tanpa deps)")
                    return True
                else:
                    logger.error(f"❌ Gagal install browser: {result2.stderr}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Error saat install browser: {e}")
            return False
            
    except ImportError:
        logger.info("⚠️ Playwright belum terinstall, mencoba install...")
        
        try:
            import subprocess
            import sys
            
            # Install playwright
            result = subprocess.run([
                sys.executable, "-m", "pip", "install", "playwright"
            ], capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                logger.info("✅ Playwright berhasil diinstall")
                
                # Install browser
                result2 = subprocess.run([
                    sys.executable, "-m", "playwright", "install", "chromium", "--with-deps"
                ], capture_output=True, text=True, timeout=300)
                
                if result2.returncode == 0:
                    logger.info("✅ Browser Playwright berhasil diinstall")
                    return True
                else:
                    logger.warning(f"⚠️ Gagal install browser: {result2.stderr}")
                    return False
            else:
                logger.error(f"❌ Gagal install Playwright: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error saat install Playwright: {e}")
            return False

async def get_fizzo_novel_list(email: str, password: str) -> Dict[str, Any]:
    """
    Mendapatkan daftar novel yang dimiliki user di fizzo.org
    
    Args:
        email: Email login fizzo.org
        password: Password login fizzo.org
        
    Returns:
        Dict dengan format:
        {
            "success": bool,
            "novels": List[Dict] dengan format [{"id": "123", "title": "Judul Novel"}],
            "count": int,
            "error": Optional[str]
        }
    """
    try:
        # Pastikan Playwright terinstall
        await install_playwright_if_needed()
        
        # Import Playwright
        try:
            from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
        except ImportError:
            return {
                "success": False,
                "novels": [],
                "count": 0,
                "error": "Playwright tidak terinstall. Silakan install dengan 'pip install playwright' dan 'playwright install chromium'"
            }
        
        # Validasi input
        if not email or not password:
            return {
                "success": False,
                "novels": [],
                "count": 0,
                "error": "Email dan password diperlukan"
            }
            
        logger.info(f"🚀 Memulai proses scraping daftar novel untuk user: {email}")
        
        # Start Playwright
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
            # Implementasi login yang lebih robust dengan pendekatan langsung
            max_retries = 3
            login_success = False
            
            for retry in range(max_retries):
                try:
                    # Step 1: Langsung ke halaman login
                    logger.info(f"🌐 Navigasi ke halaman login (percobaan {retry+1}/{max_retries})...")
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
                    logger.error(f"❌ Error saat login (percobaan {retry+1}/{max_retries}): {e}")
                    if retry < max_retries - 1:
                        wait_time = (retry + 1) * 2
                        logger.info(f"⏳ Menunggu {wait_time} detik sebelum mencoba lagi...")
                        await asyncio.sleep(wait_time)
            
            if not login_success:
                raise Exception("Gagal login setelah beberapa percobaan")
            
            # Step 7: Cari dan scrape daftar novel
            logger.info("📚 Mencari daftar novel...")
            
            # Coba cari menu Story Info atau sejenisnya
            story_info_selectors = [
                'text="Story Info"', 
                'a:has-text("Story Info")', 
                'button:has-text("Story Info")',
                'text="My Stories"',
                'a:has-text("My Stories")',
                'text="Cerita Saya"',
                'a:has-text("Cerita Saya")'
            ]
            
            story_info_found = False
            for selector in story_info_selectors:
                try:
                    if await page.is_visible(selector, timeout=2000):
                        await page.click(selector)
                        logger.info(f"✅ Berhasil mengklik menu dengan selector: {selector}")
                        await asyncio.sleep(2)
                        story_info_found = True
                        break
                except Exception as e:
                    continue
            
            if not story_info_found:
                logger.info("⚠️ Menu Story Info tidak ditemukan, mencoba scrape langsung dari dashboard")
            
            # Ambil screenshot halaman daftar novel
            await page.screenshot(path="/tmp/fizzo_novel_list.png")
            logger.info("📸 Screenshot halaman daftar novel disimpan di /tmp/fizzo_novel_list.png")
            
            # Coba berbagai selector untuk menemukan daftar novel
            novel_selectors = [
                '.novel-list .novel-item',
                '.story-list .story-item',
                '.novel-card',
                'a[href*="novel/"]',
                'a[href*="story/"]',
                '.dashboard-stories .story',
                '.story-card'
            ]
            
            for selector in novel_selectors:
                try:
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
                                if href and ('novel/' in href or 'story/' in href):
                                    if 'novel/' in href:
                                        novel_id = href.split('novel/')[1].split('/')[0]
                                    elif 'story/' in href:
                                        novel_id = href.split('story/')[1].split('/')[0]
                                
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
                except Exception as e:
                    logger.warning(f"⚠️ Error saat mencari novel dengan selector {selector}: {e}")
            
            # Deduplikasi novel berdasarkan ID
            unique_novels = []
            seen_ids = set()
            
            for novel in novels:
                if novel["id"] not in seen_ids:
                    seen_ids.add(novel["id"])
                    unique_novels.append(novel)
            
            return {
                "success": True,
                "novels": unique_novels,
                "count": len(unique_novels),
                "error": None
            }
            
        except Exception as e:
            logger.error(f"❌ Error saat scraping novel: {e}")
            return {
                "success": False,
                "novels": [],
                "count": 0,
                "error": str(e)
            }
        finally:
            await browser.close()
            await playwright.stop()
            
    except Exception as e:
        logger.error(f"❌ Error saat menjalankan get_fizzo_novel_list: {e}")
        return {
            "success": False,
            "novels": [],
            "count": 0,
            "error": str(e)
        }