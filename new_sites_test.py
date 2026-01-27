import asyncio
import httpx
import logging
from bs4 import BeautifulSoup

# Mock constants from bot.py
FIRME = "\n\n💻ANDY (el+lin2)🛠️🪛 📍Ave 3️⃣7️⃣ - #️⃣4️⃣2️⃣1️⃣1️⃣ ➗4️⃣2️⃣ y 4️⃣8️⃣ cerca del CVD 🏟️ 📌MAYABEQUE SAN JOSÉ"
logger = logging.getLogger(__name__)

async def search_danfra(query: str):
    """Buscar en Danfra.com"""
    try:
        async with httpx.AsyncClient() as client:
            url = "https://www.danfra.com/ajax/search"
            response = await client.post(url, data={'search_text': query}, timeout=10)
            response.raise_for_status()
            data = response.json()

        if not data:
            return None, None

        # Tomamos el primer resultado
        item = data[0]
        title = item.get('nombre', 'Sin título')
        slug = item.get('slug', '')
        image_path = item.get('foto', '')
        image_url = f"https://www.danfra.com/{image_path}" if image_path else None
        page_url = f"https://www.danfra.com/serie/{slug}/" if item.get('tipo') == 'serie' else f"https://www.danfra.com/novela/{slug}/"

        caption = f"🎬 <b>{title} (Danfra)</b>\n\n"
        caption += f"🔗 <a href='{page_url}'>Ver en Danfra</a>\n"
        caption += f"\n¡No te pierdas esta emocionante historia! 🚀{FIRME}"

        return image_url, caption

    except Exception as e:
        print(f"Error en Danfra: {e}")
        return None, None


async def search_lamparaturca(query: str):
    """Buscar en Lamparaturca.com"""
    try:
        async with httpx.AsyncClient() as client:
            url = f"https://lamparaturca.com/?s={query}"
            response = await client.get(url, timeout=10)
            response.raise_for_status()
            
        soup = BeautifulSoup(response.text, 'html.parser')
        article = soup.find('article')
        
        if not article:
            return None, None

        title_tag = article.find('h2', class_='entry-title') or article.find('h1', class_='entry-title')
        if not title_tag:
            return None, None
            
        title = title_tag.get_text(strip=True)
        link = title_tag.find('a')['href'] if title_tag.find('a') else f"https://lamparaturca.com/?s={query}"
        
        img_tag = article.find('img')
        image_url = img_tag['src'] if img_tag else None

        caption = f"🎬 <b>{title} (Lámpara Turca)</b>\n\n"
        caption += f"🔗 <a href='{link}'>Ver en Lámpara Turca</a>\n"
        caption += f"\n¡Una historia fascinante te espera! ✨{FIRME}"

        return image_url, caption

    except Exception as e:
        print(f"Error en Lámpara Turca: {e}")
        return None, None

async def main():
    print("🔍 Testing Danfra search for 'Una nueva vida'...")
    img, cap = await search_danfra("Una nueva vida")
    if cap:
        print(f"✅ Danfra success!\nImage: {img}\nCaption: {cap[:100]}...")
    else:
        print("❌ Danfra failed")

    print("\n🔍 Testing Lámpara Turca search for 'Bahar'...")
    img, cap = await search_lamparaturca("Bahar")
    if cap:
        print(f"✅ Lámpara Turca success!\nImage: {img}\nCaption: {cap[:100]}...")
    else:
        print("❌ Lámpara Turca failed")

if __name__ == "__main__":
    asyncio.run(main())
