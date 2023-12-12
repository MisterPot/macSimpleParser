import asyncio
import dataclasses
import json
import urllib.parse

from httpx import AsyncClient
from playwright.async_api import (
    Playwright,
    async_playwright,
    BrowserContext
)
from bs4 import BeautifulSoup


@dataclasses.dataclass
class MenuItem:
    name: str
    description: str
    calories: str
    fats: str
    carbs: str
    proteins: str
    unsaturated_fats: str
    sugar: str
    salt: str
    portion: str


class MacParser:

    BASE_URL = 'https://www.mcdonalds.com'

    def __init__(
            self,
            session: AsyncClient,
            context: BrowserContext,
            max_sim_pages: int
    ):
        self.session = session
        self.context = context
        self.max_sim_pages = max_sim_pages

    @classmethod
    async def create(
            cls,
            playwright: Playwright,
            max_sim_pages: int = 5,
            **browser_options
    ) -> "MacParser":
        session = AsyncClient(
            headers={
                'User-Agent': "Mozilla/5.0 (Windows; U; Windows NT 5.0) AppleWebKit/537.1.1 (KHTML, like Gecko) "
                              "Chrome/28.0.873.0 Safari/537.1.1"
            }
        )
        await session.__aenter__()
        browser = await playwright.chromium.launch(**browser_options)
        context = await browser.new_context()
        return cls(session, context, max_sim_pages=max_sim_pages)

    async def fetch_menu(self) -> list[MenuItem]:
        main_menu = await self.session.get(
            url=urllib.parse.urljoin(self.BASE_URL, '/ua/uk-ua/eat/fullmenu.html')
        )
        soup = BeautifulSoup(main_menu.content, 'html.parser')
        links = soup.find_all(attrs={"class": 'cmp-category__item-link'})
        semaphore = asyncio.Semaphore(self.max_sim_pages)
        return await asyncio.gather(*[
            self._parse_item(
                item_link=urllib.parse.urljoin(self.BASE_URL, link_item.attrs['href']),
                semaphore=semaphore
            )
            for link_item in links
        ])

    async def _parse_item(self, item_link: str, semaphore: asyncio.Semaphore) -> MenuItem:
        async with semaphore:
            page = await self.context.new_page()
            await page.goto(item_link)
            page_content = await page.content()
            soup = BeautifulSoup(page_content, 'html.parser')
            item_name = self._take_string_opt(soup, 'span.cmp-product-details-main__heading-title')
            item = MenuItem(
                name=item_name,
                description=self._take_string_opt(soup, 'div.cmp-product-details-main__description'),
                calories=self._take_hidden(soup, 'li.cmp-nutrition-summary__heading-primary-item:nth-child(1) span['
                                                 'aria-hidden]:not([''class])'),
                fats=self._take_hidden(soup, 'li.cmp-nutrition-summary__heading-primary-item:nth-child(2) span['
                                             'aria-hidden]:not([class])'),
                carbs=self._take_hidden(soup, 'li.cmp-nutrition-summary__heading-primary-item:nth-child(3) span['
                                              'aria-hidden]:not([class])'),
                proteins=self._take_hidden(soup, 'li.cmp-nutrition-summary__heading-primary-item:nth-child(4) span['
                                                 'aria-hidden]:not([class])'),
                unsaturated_fats=self._take_hidden(soup, 'div.cmp-nutrition-summary__details-column-view-desktop '
                                                   'li.label-item:nth-child(1) > span:nth-child(2) span['
                                                   'aria-hidden]:not([class])'),
                sugar=self._take_hidden(soup, 'div.cmp-nutrition-summary__details-column-view-desktop '
                                              'li.label-item:nth-child(2) > span:nth-child(2) span[aria-hidden]:not(['
                                              'class])'),
                salt=self._take_hidden(soup, 'div.cmp-nutrition-summary__details-column-view-desktop '
                                             'li.label-item:nth-child(3) > span:nth-child(2) span[aria-hidden]:not(['
                                             'class])'),
                portion=self._take_hidden(soup, 'div.cmp-nutrition-summary__details-column-view-desktop '
                                                'li.label-item:nth-child(4) > span:nth-child(2) span['
                                                'aria-hidden]:not([class])')
            )
            await page.close()
            print(f'Item parsed - "{item_name}"')
            return item

    @staticmethod
    def _take_hidden(soup: BeautifulSoup, selector: str) -> str:
        selected = soup.select(selector)
        return '\n'.join(tag.text.strip() for tag in selected)

    @staticmethod
    def _take_string_opt(soup: BeautifulSoup, selector: str) -> str:
        selected = soup.select_one(selector)
        if selected:
            return selected.text.strip()
        return ""


async def main() -> None:
    playwright = await async_playwright().start()
    parser = await MacParser.create(playwright, max_sim_pages=6, headless=False)
    menu = await parser.fetch_menu()
    await playwright.stop()

    with open('data.json', 'w', encoding='utf-8') as file:
        json.dump([
            item.__dict__ for item in menu
        ], file, indent=4, ensure_ascii=False)


if __name__ == '__main__':
    asyncio.run(main())
