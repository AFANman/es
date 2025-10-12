import os
from datetime import datetime
import re
import sys
from typing import Dict, List, Tuple

try:
    from crawl4ai import WebCrawler, BrowserConfig, CrawlConfig
    HAS_CRAWL4AI = True
except Exception:
    HAS_CRAWL4AI = False

import requests
from bs4 import BeautifulSoup
import pandas as pd


def crawl_page(url: str) -> Tuple[str, str]:
    """Return (html, markdown) using Crawl4AI if available, else requests.
    """
    if HAS_CRAWL4AI:
        try:
            browser_cfg = BrowserConfig(headless=True)
            crawler = WebCrawler(browser_config=browser_cfg)
            # Minimal config; allow JS for dynamic pages
            crawl_cfg = CrawlConfig()
            result = crawler.crawl(url=url, config=crawl_cfg)
            html = result.html or ""
            md = getattr(result, "markdown", "") or ""
            if html.strip():
                return html, md
        except Exception:
            pass

    # Fallback
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    return resp.text, ""


def find_card_links_loose(soup: BeautifulSoup, base_url: str) -> List[str]:
    """Looser finder for detail links on listing pages.
    - Collect anchors whose href contains '/ensemble-star-music/<digits>'
    - Prefer within the "スカウト追加カード" section but fallback to whole page
    - Do NOT require bracketed text on anchor; normalize to absolute URLs
    """
    urls: List[str] = []
    base_id = re.search(r"ensemble-star-music/(\d+)", base_url)
    base_id_str = base_id.group(1) if base_id else None

    section = soup.find(lambda t: t.name in {"h2", "h3", "div", "section"} and "スカウト追加カード" in t.get_text("\n", strip=True))
    anchors: List[Tuple[str, str]] = []
    if section:
        cur = section
        for _ in range(40):
            cur = cur.find_next_sibling()
            if not cur:
                break
            txt = cur.get_text("\n", strip=True)
            if any(k in txt for k in ["★ リンク一覧", "キャラクター", "IRマス詳細", "必要素材数"]):
                break
            for a in cur.find_all('a', href=True):
                anchors.append((a['href'], a.get_text(strip=True)))
    else:
        for a in soup.find_all('a', href=True):
            anchors.append((a['href'], a.get_text(strip=True)))

    for href, _ in anchors:
        if 'ensemble-star-music/' not in href:
            continue
        m = re.search(r"ensemble-star-music/(\d+)", href)
        if not m:
            continue
        card_id = m.group(1)
        if not card_id or card_id == base_id_str:
            continue
        if href.startswith('http'):
            urls.append(href)
        else:
            urls.append('https://gamerch.com/' + href.lstrip('/'))
    # Deduplicate & cap
    seen = set()
    dedup: List[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            dedup.append(u)
            if len(dedup) >= 100:
                break
    return dedup


def find_card_links(soup: BeautifulSoup, base_url: str) -> List[str]:
    """Find detail page links for cards from a listing/campaign page.
    Heuristics:
    - anchors whose href contains '/ensemble-star-music/<digits>'
    - anchor text contains a full-width bracketed card name like ［...］
    - exclude the base url itself
    Limit to a reasonable number to avoid long runs.
    """
    urls: List[str] = []
    base_id = re.search(r"ensemble-star-music/(\d+)", base_url)
    base_id_str = base_id.group(1) if base_id else None

    # Narrow to the section titled "スカウト追加カード" when present
    section = soup.find(lambda t: t.name in {"h2", "h3", "div", "section"} and "スカウト追加カード" in t.get_text("\n", strip=True))
    anchors: List[Tuple[str, str]] = []
    if section:
        cur = section
        for _ in range(30):
            cur = cur.find_next_sibling()
            if not cur:
                break
            txt = cur.get_text("\n", strip=True)
            # Stop at next major navigation or unrelated blocks
            if any(k in txt for k in ["★ リンク一覧", "キャラクター", "IRマス詳細", "必要素材数"]):
                break
            for a in cur.find_all('a', href=True):
                anchors.append((a['href'], a.get_text(strip=True)))
    else:
        # Fallback to all anchors
        for a in soup.find_all('a', href=True):
            anchors.append((a['href'], a.get_text(strip=True)))

    for href, text in anchors:
        if 'ensemble-star-music/' not in href:
            continue
        m = re.search(r"ensemble-star-music/(\d+)", href)
        if not m:
            continue
        card_id = m.group(1)
        if not card_id or card_id == base_id_str:
            continue
        # Require bracketed title to reduce noise on listing pages
        if not re.search(r"\uFF3B[^\uFF3D]+\uFF3D", text):
            continue
        # Normalize absolute URL
        if href.startswith('http'):
            urls.append(href)
        else:
            urls.append('https://gamerch.com/' + href.lstrip('/'))
    # Deduplicate preserving order and cap to 60
    seen = set()
    dedup: List[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            dedup.append(u)
            if len(dedup) >= 60:
                break
    return dedup


def parse_card_name(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    # Prefer og:title
    og = soup.find("meta", attrs={"property": "og:title"})
    if og and og.get("content"):
        title = og["content"].strip()
        # Try to extract bracketed card name
        m = re.search(r"\uFF3B([^\uFF3D]+)\uFF3D\s*([^\-|]+)", title)  # ［...］ Name
        if m:
            return f"［{m.group(1).strip()}］{m.group(2).strip()}"
        return title
    # Fallback to h1
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    # Last resort: page title
    if soup.title and soup.title.string:
        t = soup.title.string.strip()
        m = re.search(r"\uFF3B([^\uFF3D]+)\uFF3D\s*([^\-|]+)", t)
        if m:
            return f"［{m.group(1).strip()}］{m.group(2).strip()}"
        return t
    return ""


def extract_event_name_from_listing(soup: BeautifulSoup) -> str:
    """Extract the event/scout name from listing page.
    Priority:
    1) Text containing 'クロススカウト・' and '／inspired' or '／empathy'
    2) Any text containing 'アンビバレンス' with 'クロススカウト'
    3) Page title stripped of site prefix like '【あんスタMusic】'
    """
    full_text = soup.get_text("\n", strip=True)
    # 1) Explicit inspired/empathy
    m = re.search(r"(クロススカウト・[^\n／]+／(?:inspired|empathy))", full_text)
    if m:
        return m.group(1).strip()
    # 2) クロススカウト＋アンビバレンス
    m = re.search(r"(クロススカウト・[^\n]*アンビバレンス[^\n]*)", full_text)
    if m:
        return m.group(1).strip()
    # 3) Title fallback
    if soup.title and soup.title.string:
        t = soup.title.string.strip()
        # Remove leading site mark
        t = re.sub(r"^【あんスタMusic】", "", t)
        t = re.sub(r"\s*-\s*あんスタMusic攻略wiki\s*\|\s*Gamerch\s*$", "", t)
        return t.strip()
    return ""


def extract_additional_cards_from_listing(soup: BeautifulSoup) -> List[Dict[str, str]]:
    """Extract additional cards under the listing page without visiting detail pages.
    Strategy: parse the "スカウトの確率について" block that enumerates ☆5/☆4/☆3 cards
    and map bracketed names to rarities.
    Returns a list of rows with at least 卡面名称, レアリティ, イベント名.
    """
    text = soup.get_text("\n", strip=True)
    rows: List[Dict[str, str]] = []
    event_name = extract_event_name_from_listing(soup)
    # Collect bracketed names directly from DOM text nodes to be robust
    collected: List[str] = []
    for tnode in soup.find_all(string=re.compile(r"［[^］]+］")):
        s = (tnode.strip() if isinstance(tnode, str) else str(tnode)).strip()
        # Expect format like "［裏表アンビバレンス］HiMERU"
        if not s or "アンビバレンス" not in s:
            continue
        if s.startswith("☆"):
            # Skip lines annotated with star at beginning (likely unrelated samples)
            continue
        # Normalize whitespace
        s = re.sub(r"\s+", " ", s)
        if s not in collected:
            collected.append(s)
        if len(collected) >= 3:
            break

    # Assign rarities by appearance order: ☆5, ☆4, ☆3
    rarity_order = ["☆5", "☆4", "☆3"]
    for idx, name in enumerate(collected[:3]):
        rarity = rarity_order[idx] if idx < len(rarity_order) else ""
        rows.append({
            "卡面名称": name,
            "レアリティ": rarity,
            "イベント名": event_name,
        })
    return rows


def extract_basic_info(soup: BeautifulSoup) -> Dict[str, str]:
    info = {
        "レアリティ": "",
        "タイプ/属性": "",
        "ファン上限": "",
        "追加日": "",
    }
    # Find a block that contains 基本情報
    block = soup.find(lambda t: t.name in {"h2", "h3", "div", "section"} and "基本情報" in t.get_text("\n", strip=True))
    text = ""
    if block:
        # Gather some siblings to include actual content
        texts = [block.get_text("\n", strip=True)]
        sib = block.find_next_sibling()
        for _ in range(5):
            if not sib:
                break
            texts.append(sib.get_text("\n", strip=True))
            sib = sib.find_next_sibling()
        text = "\n".join(texts)
    else:
        # Broader text search
        text = soup.get_text("\n", strip=True)

    # Try table-like label-value extraction
    def find_label(label: str) -> str:
        tag = soup.find(string=re.compile(label))
        if tag:
            parent = getattr(tag, 'parent', None)
            if parent:
                # Same-line value
                full = parent.get_text("\n", strip=True)
                m = re.search(label + r"\s*([^\n]+)", full)
                if m:
                    return m.group(1).strip()
                # Next sibling value
                for sib in parent.find_next_siblings():
                    val = sib.get_text("\n", strip=True)
                    if val:
                        return val
        return ""

    info["レアリティ"] = info["レアリティ"] or find_label("レアリティ")
    info["タイプ/属性"] = info["タイプ/属性"] or find_label("タイプ/属性")
    info["ファン上限"] = info["ファン上限"] or find_label("ファン上限")
    info["追加日"] = info["追加日"] or find_label("追加日")

    # Simple regex extractions
    m = re.search(r"レアリティ\s*([☆★]?\d+)", text)
    if m:
        info["レアリティ"] = m.group(1)
    m = re.search(r"タイプ/属性\s*([^\n]+)", text)
    if m:
        info["タイプ/属性"] = m.group(1).strip()
    m = re.search(r"(無凸)?ファン上限\s*([0-9,]+)\s*人?", text)
    if m:
        info["ファン上限"] = m.group(2).replace(",", "")
    # 追加日取整行（优先首个匹配的整行）
    m = re.search(r"^追加日\s*([^\n]+)$", text, re.M)
    if m:
        info["追加日"] = m.group(1).strip()
    return info


def extract_status(soup: BeautifulSoup) -> Dict[str, Dict[str, str]]:
    # status[列][行] = 値  e.g., status['初期値']['総合値'] = '23510'
    status: Dict[str, Dict[str, str]] = {}
    target_table = None
    for table in soup.find_all("table"):
        t = table.get_text("\n", strip=True)
        if all(k in t for k in ["総合値", "Da", "Vo", "Pf"]):
            target_table = table
            break
    if not target_table:
        return status

    # Extract column headers (初期値 / 無凸MAX値 / 完凸MAX値)
    columns: List[str] = []
    for tr in target_table.find_all("tr"):
        cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
        if any(x in cells for x in ["初期値", "無凸MAX値", "完凸MAX値"]):
            # First cell likely row header placeholder
            if len(cells) >= 2:
                columns = [c for c in cells[1:] if c]
            break
    if not columns:
        columns = ["初期値", "無凸MAX値", "完凸MAX値"]

    def as_num(s: str) -> str:
        s = s.replace(",", "").replace("-", "").strip()
        return s

    for tr in target_table.find_all("tr"):
        cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
        if not cells:
            continue
        row_label = cells[0]
        if row_label in ["総合値", "Da", "Vo", "Pf"]:
            for idx, col in enumerate(columns):
                if idx + 1 < len(cells):
                    status.setdefault(col, {})[row_label] = as_num(cells[idx + 1])
    return status


def extract_skills(soup: BeautifulSoup) -> Dict[str, Dict[str, str]]:
    skills = {
        "センタースキル": {"名称": "", "効果": ""},
        "ライブスキル": {"名称": "", "効果": ""},
        "サポートスキル": {"名称": "", "効果": ""},
    }

    full_text = soup.get_text("\n", strip=True)

    # Narrow to skills section when possible
    section_start = full_text.find("センター/ライブ/サポートスキル")
    skills_text = full_text
    if section_start != -1:
        skills_text = full_text[section_start:]
        # Cut at next major section
        for marker in ["スカウト画面", "アイドルロード", "取得できるスキル/アイテム", "必要素材数"]:
            idx = skills_text.find(marker)
            if idx != -1:
                skills_text = skills_text[:idx]
                break

    # Center skill: prefer explicit name format then fallback to line scanning
    center_name = skills["センタースキル"]["名称"]
    center_eff = skills["センタースキル"]["効果"]
    m_center_name_inline = re.search(r"センタースキル\s*「([^」]+)」", full_text)
    if m_center_name_inline:
        center_name = m_center_name_inline.group(1).strip()
    for line in full_text.splitlines():
        if (not center_name) and "センタースキル" in line:
            name = line.split("センタースキル", 1)[-1].strip()
            # filter out navigation/common labels
            if name and not re.search(r"効果|共通|項目", name):
                center_name = name
        if (not center_eff) and ("固定" in line or "タイプ" in line) and ("％" in line or re.search(r"\bup\b|\bUP\b", line)):
            center_eff = line.strip()
        if center_name and center_eff:
            break
    # Derive a reasonable name from effect if name missing
    if not center_name and center_eff:
        m = re.search(r"([A-Za-zァ-ンヴー]+)タイプの(Da|Vo|Pf).*?％up", center_eff)
        if m:
            center_name = f"{m.group(1)}タイプ {m.group(2)}アップ"
    skills["センタースキル"]["名称"] = center_name
    skills["センタースキル"]["効果"] = center_eff

    # Live skill
    m_name = re.search(r"ライブスキル\s*「?([^\n」]+)」?", full_text)
    if m_name:
        skills["ライブスキル"]["名称"] = m_name.group(1).strip()
    # Collect level lines within ライブスキル block
    m_live_block = re.search(r"ライブスキル[\s\S]*?(初期Lv\.[^\n]+(?:\n|$)[\s\S]*?)(?:サポートスキル|\n\n)", skills_text)
    if m_live_block:
        block = m_live_block.group(1)
        live_lines: List[str] = []
        for line in block.splitlines():
            if re.search(r"Lv\.[0-9]+：", line):
                live_lines.append(line.strip())
        if live_lines:
            skills["ライブスキル"]["効果"] = " / ".join(live_lines)
    
    # Support skill
    m_sup_block = re.search(r"サポートスキル\s*「?([^\n」]+)」?\n?([\s\S]+?)(?:アイドルロード|取得できるスキル|必要素材数|\n\n)", skills_text)
    if m_sup_block:
        skills["サポートスキル"]["名称"] = (m_sup_block.group(1) or "").strip()
        sup_lines: List[str] = []
        for line in (m_sup_block.group(2) or "").splitlines():
            if re.search(r"Lv\.[0-9]+：", line) or re.search(r"ドロップ率", line):
                sup_lines.append(line.strip())
        if sup_lines:
            skills["サポートスキル"]["効果"] = " / ".join(sup_lines)
    # Fallback scanning for support
    if not skills["サポートスキル"]["名称"]:
        for line in full_text.splitlines():
            m = re.search(r"サポートスキル\s*「?([^\n」]+)」?", line)
            if m:
                skills["サポートスキル"]["名称"] = m.group(1).strip()
                break
    if not skills["サポートスキル"]["効果"]:
        sup_lines: List[str] = []
        for line in full_text.splitlines():
            if re.search(r"ドロップ率", line) or re.search(r"Lv\.[0-9]+：", line):
                sup_lines.append(line.strip())
        if sup_lines:
            skills["サポートスキル"]["効果"] = " / ".join(sup_lines)

    return skills


def extract_road_items(soup: BeautifulSoup) -> str:
    # Prefer DOM-based extraction: find heading then collect following content until next section
    heading = soup.find(lambda t: t.name in {"h2", "h3", "div", "section"} and "取得できるスキル/アイテム" in t.get_text("\n", strip=True))
    if heading:
        items: List[str] = []
        cur = heading
        # Walk a few siblings to capture lists and paragraphs
        for _ in range(8):
            cur = cur.find_next_sibling()
            if not cur:
                break
            txt = cur.get_text("\n", strip=True)
            if not txt:
                continue
            if any(k in txt for k in ["必要素材数", "IRマス詳細", "合計ステータス", "横にスクロール"]):
                break
            # collect meaningful lines
            for ln in txt.splitlines():
                ln = ln.strip()
                if not ln:
                    continue
                if re.search(r"(スキル|ピース|アイテム|MV|ルーム衣装|SPP|背景|ボイス)", ln):
                    items.append(ln)
        if items:
            return "；".join(items)

    # Fallback: text block between headings
    text = soup.get_text("\n", strip=True)
    m = re.search(r"取得できるスキル/アイテム\n([\s\S]+?)(?:必要素材数|IRマス詳細|合計ステータス|横にスクロール|\n\n)", text)
    if m:
        lines = [ln.strip() for ln in m.group(1).splitlines() if ln.strip()]
        picks = []
        for ln in lines:
            if re.search(r"(スキル|ピース|アイテム|MV|ルーム衣装|SPP|背景|ボイス)", ln):
                picks.append(ln)
        if not picks:
            return ""
        return "；".join(picks)

    # Last resort: robust line scanning
    items: List[str] = []
    for ln in text.splitlines():
        if re.match(r"^(ライブスキル「.+」|サポートスキル「.+」|MV衣装.+|ルーム衣装.+|SPP.+)$", ln.strip()):
            items.append(ln.strip())
    return "；".join(items)


def build_row(card_name: str, basic: Dict[str, str], status: Dict[str, Dict[str, str]], skills: Dict[str, Dict[str, str]], road_items: str) -> Dict[str, str]:
    row = {
        "卡面名称": card_name,
        "レアリティ": basic.get("レアリティ", ""),
        "タイプ/属性": basic.get("タイプ/属性", ""),
        "ファン上限": basic.get("ファン上限", ""),
        "追加日": basic.get("追加日", ""),
        "イベント名": "",
        "初期値 総合値": status.get("初期値", {}).get("総合値", ""),
        "初期値 Da": status.get("初期値", {}).get("Da", ""),
        "初期値 Vo": status.get("初期値", {}).get("Vo", ""),
        "初期値 Pf": status.get("初期値", {}).get("Pf", ""),
        "無凸MAX値 総合値": status.get("無凸MAX値", {}).get("総合値", ""),
        "無凸MAX値 Da": status.get("無凸MAX値", {}).get("Da", ""),
        "無凸MAX値 Vo": status.get("無凸MAX値", {}).get("Vo", ""),
        "無凸MAX値 Pf": status.get("無凸MAX値", {}).get("Pf", ""),
        "完凸MAX値 総合値": status.get("完凸MAX値", {}).get("総合値", ""),
        "完凸MAX値 Da": status.get("完凸MAX値", {}).get("Da", ""),
        "完凸MAX値 Vo": status.get("完凸MAX値", {}).get("Vo", ""),
        "完凸MAX値 Pf": status.get("完凸MAX値", {}).get("Pf", ""),
        "センタースキル 名称": skills.get("センタースキル", {}).get("名称", ""),
        "センタースキル 効果": skills.get("センタースキル", {}).get("効果", ""),
        "ライブスキル 名称": skills.get("ライブスキル", {}).get("名称", ""),
        "ライブスキル 効果": skills.get("ライブスキル", {}).get("効果", ""),
        "サポートスキル 名称": skills.get("サポートスキル", {}).get("名称", ""),
        "サポートスキル 効果": skills.get("サポートスキル", {}).get("効果", ""),
        "取得できるスキル/アイテム": road_items,
    }
    return row


def map_to_template(row: Dict[str, str], columns_order: List[str]) -> Dict[str, str]:
    """Map parsed row (Japanese keys) to template columns (Chinese keys)."""
    def pick_stat(key: str) -> str:
        # Prefer 完凸MAX値 then 無凸MAX値 then 初期値
        return (
            row.get(f"完凸MAX値 {key}")
            or row.get(f"無凸MAX値 {key}")
            or row.get(f"初期値 {key}")
            or ""
        )

    # Parse live Lv5 from combined effect
    live_eff = row.get("ライブスキル 効果", "") or ""
    m_lv5 = re.search(r"Lv\.5：([^/\n]+)", live_eff)
    live_lv5 = m_lv5.group(1).strip() if m_lv5 else ""

    # Parse support Lv3 from combined effect
    sup_eff = row.get("サポートスキル 効果", "") or ""
    m_lv3 = re.search(r"Lv\.3：([^/\n]+)", sup_eff)
    sup_lv3 = m_lv3.group(1).strip() if m_lv3 else ""

    # Split road items
    mv_items: List[str] = []
    room_items: List[str] = []
    bg_items: List[str] = []
    spp_tracks: List[str] = []
    for it in (row.get("取得できるスキル/アイテム", "") or "").split("；"):
        it = it.strip()
        if not it:
            continue
        if it.startswith("MV衣装"):
            mv_items.append(it)
        elif it.startswith("ルーム衣装"):
            room_items.append(it)
        elif it.startswith("背景"):
            bg_items.append(it)
        elif it.startswith("SPP"):
            spp_tracks.append(it)

    # Card name with star suffix
    name = row.get("卡面名称", "")
    rarity = (row.get("レアリティ", "") or "").strip()
    if rarity and not rarity.startswith("☆"):
        # Normalize e.g. '5' -> '☆5'
        if re.match(r"^\d+$", rarity):
            rarity = f"☆{rarity}"
    if name and rarity:
        name = f"{name} {rarity}"

    mapped = {
        "卡面名称": name,
        "活动名称": row.get("イベント名", ""),
        "center技能名称": row.get("センタースキル 名称", ""),
        "live技能名": row.get("ライブスキル 名称", ""),
        "support技能名": row.get("サポートスキル 名称", ""),
        "Unnamed: 4": "",
        "DA": pick_stat("Da"),
        "VO": pick_stat("Vo"),
        "PF": pick_stat("Pf"),
        "综合值": pick_stat("総合値"),
        "center技能": row.get("センタースキル 効果", ""),
        "live技能（lv5）": live_lv5,
        "support技能（lv3）": sup_lv3,
        "MV衣装": " / ".join(mv_items),
        "房间衣装": " / ".join(room_items),
        "背景": " / ".join(bg_items),
        "spp对应乐曲": " / ".join(spp_tracks),
        "故事": "",
    }
    # Preserve order: only include known columns; missing -> empty
    return {col: mapped.get(col, "") for col in columns_order}


def write_excel_rows(out_path: str, rows: List[Dict[str, str]], columns_order: List[str]) -> None:
    normalized = [{col: r.get(col, "") for col in columns_order} for r in rows]
    df = pd.DataFrame(normalized, columns=columns_order)
    df.to_excel(out_path, index=False)


def main() -> None:
    # Accept URL from argv or stdin
    if len(sys.argv) > 1 and sys.argv[1].strip():
        url = sys.argv[1].strip()
    else:
        print("请输入卡面页面链接（例如 https://gamerch.com/ensemble-star-music/918821 ）:")
        url = input().strip()
    if not url:
        print("未输入链接，程序退出。")
        return
    try:
        html, md = crawl_page(url)
    except Exception as e:
        print(f"抓取失败: {e}")
        return

    soup = BeautifulSoup(html, "lxml")
    # Detect whether current page is a card detail page (with bracketed title)
    preview_name = parse_card_name(html)
    full_text = soup.get_text("\n", strip=True)
    # Prefer text-based detection: treat as listing when typical markers are present
    has_scout_section = any(k in full_text for k in ["スカウト追加カード", "追加カード", "スカウトの確率について", "クロススカウト・"])
    # Detail page heuristic: requires bracketed card title
    is_detail = bool(re.search(r"\uFF3B[^\uFF3D]+\uFF3D", preview_name))

    # Try to collect detail links (☆5/☆4/☆3) from the list page under "スカウト追加カード"
    links = [] if is_detail else find_card_links(soup, url)
    rows: List[Dict[str, str]] = []
    # Attempt text-based listing extraction first when page is not a detail page
    if not is_detail:
        base_rows = extract_additional_cards_from_listing(soup)
        target_names = [r.get("卡面名称", "") for r in base_rows]
        event_name = base_rows[0].get("イベント名", "") if base_rows else ""
        # Prefer strict links; if none, use loose finder
        candidate_links = links if links else find_card_links_loose(soup, url)
        picked = 0
        for link in candidate_links:
            try:
                h, _ = crawl_page(link)
                sp = BeautifulSoup(h, "lxml")
                card_name = parse_card_name(h)
                if card_name and card_name in target_names:
                    basic = extract_basic_info(sp)
                    status = extract_status(sp)
                    skills = extract_skills(sp)
                    road_items = extract_road_items(sp)
                    row = build_row(card_name, basic, status, skills, road_items)
                    row["イベント名"] = event_name
                    # Use listing rarity when available
                    for br in base_rows:
                        if br.get("卡面名称") == card_name and br.get("レアリティ"):
                            row["レアリティ"] = br["レアリティ"]
                            break
                    rows.append(row)
                    picked += 1
                    if picked >= 3:
                        break
            except Exception:
                continue
    if links:
        print(f"检测到列表页，拟抓取 {len(links)} 个卡面详情……")
        for link in links:
            try:
                h, _ = crawl_page(link)
                sp = BeautifulSoup(h, "lxml")
                card_name = parse_card_name(h)
                basic = extract_basic_info(sp)
                status = extract_status(sp)
                skills = extract_skills(sp)
                road_items = extract_road_items(sp)
                row = build_row(card_name, basic, status, skills, road_items)
                # Extract event name from 追加日: e.g. 2025年04月25日（クロススカウト・アンビバレンス／inspired）
                add = row.get("追加日", "")
                m_event = re.search(r"追加日[^\n]*（([^）]+)）", add)
                if m_event:
                    row["イベント名"] = m_event.group(1).strip()
                rows.append(row)
            except Exception:
                continue
    elif rows:
        # Already parsed from listing + detail matching
        pass
    else:
        # Fallback: single card page
        print("检测到卡面详情页，正在解析……")
        card_name = parse_card_name(html)
        basic = extract_basic_info(soup)
        status = extract_status(soup)
        skills = extract_skills(soup)
        road_items = extract_road_items(soup)
        row = build_row(card_name, basic, status, skills, road_items)
        add = row.get("追加日", "")
        m_event = re.search(r"追加日[^\n]*（([^）]+)）", add)
        if m_event:
            row["イベント名"] = m_event.group(1).strip()
        rows.append(row)

    # Load template columns order
    base_dir = os.path.dirname(os.path.dirname(__file__))
    template_path = os.path.join(base_dir, "es2 卡面名称及技能一览（新表）示例.xlsx")
    try:
        tmpl_df = pd.read_excel(template_path)
        columns_order = tmpl_df.columns.tolist()
        # Insert 活动名称 列（置于第一列），如果不存在
        if "活动名称" not in columns_order:
            columns_order = ["活动名称"] + columns_order
    except Exception:
        columns_order = list(rows[0].keys()) if rows else []

    # Timestamped output filename
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_name = f"es2 卡面名称及技能一览{ts}.xlsx"
    out_path = os.path.join(base_dir, out_name)
    # Map rows directly; 活动名称 列承载活动信息，不再插入头部行
    final_rows: List[Dict[str, str]] = [map_to_template(r, columns_order) for r in rows] if rows and columns_order else rows
    write_excel_rows(out_path, final_rows, columns_order)
    print(f"已输出: {out_path}")


if __name__ == "__main__":
    main()