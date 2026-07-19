import logging
import httpx

logger = logging.getLogger(__name__)

async def fetch_codeforces_stats(client: httpx.AsyncClient, handle: str) -> dict | None:
    """Fetch user rating, rank, and solved languages/tags from Codeforces public REST API."""
    if not handle:
        return None
        
    try:
        # 1. Fetch user info
        info_url = f"https://codeforces.com/api/user.info?handles={handle}"
        info_resp = await client.get(info_url, timeout=10)
        
        if info_resp.status_code != 200:
            logger.warning(f"Codeforces user info API returned status {info_resp.status_code} for {handle}")
            return None
            
        info_data = info_resp.json()
        if info_data.get("status") != "OK" or not info_data.get("result"):
            return None
            
        user_info = info_data["result"][0]
        
        # 2. Fetch submissions for tags and languages
        status_url = f"https://codeforces.com/api/user.status?handle={handle}&from=1&count=100"
        status_resp = await client.get(status_url, timeout=10)
        
        languages = set()
        tags = set()
        solved_count = 0
        solved_problem_ids = set()
        
        if status_resp.status_code == 200:
            status_data = status_resp.json()
            if status_data.get("status") == "OK":
                for sub in status_data.get("result", []):
                    if sub.get("verdict") == "OK":
                        # Deduplicate by problem ID
                        problem = sub.get("problem", {})
                        prob_id = f"{problem.get('contestId')}-{problem.get('index')}"
                        
                        # Add language
                        lang = sub.get("programmingLanguage", "")
                        # Normalize language name (e.g. "GNU C++17" -> "C++")
                        normalized_lang = _normalize_cf_language(lang)
                        if normalized_lang:
                            languages.add(normalized_lang)
                            
                        # Add tags
                        for tag in problem.get("tags", []):
                            tags.add(tag)
                            
                        if prob_id not in solved_problem_ids:
                            solved_problem_ids.add(prob_id)
                            solved_count += 1

        return {
            "username": handle,
            "rating": user_info.get("rating"),
            "rank": user_info.get("rank"),
            "max_rating": user_info.get("maxRating"),
            "max_rank": user_info.get("maxRank"),
            "solved_count": solved_count,
            "languages": list(languages),
            "tags": list(tags)
        }
    except Exception as e:
        logger.error(f"Codeforces API analysis failed for {handle}: {e}")
        return None

def _normalize_cf_language(lang: str) -> str | None:
    lang_lower = lang.lower()
    if "c++" in lang_lower:
        return "C++"
    if "python" in lang_lower or "pypy" in lang_lower:
        return "Python"
    if "java" in lang_lower:
        return "Java"
    if "kotlin" in lang_lower:
        return "Kotlin"
    if "go" in lang_lower:
        return "Go"
    if "rust" in lang_lower:
        return "Rust"
    if "c#" in lang_lower:
        return "C#"
    if "javascript" in lang_lower or "js" in lang_lower:
        return "JavaScript"
    return None

async def fetch_leetcode_stats(client: httpx.AsyncClient, username: str) -> dict | None:
    """Fetch solved counts and languages from LeetCode public GraphQL endpoint.
    Wrapped in try-except to degrade gracefully if LeetCode blocks our requests."""
    if not username:
        return None
        
    url = "https://leetcode.com/graphql"
    query = """
    query userProblemsSolved($username: String!) {
      matchedUser(username: $username) {
        submitStatsGlobal {
          acSubmissionNum {
            difficulty
            count
          }
        }
        languageProblemCount {
          languageName
          problemsSolved
        }
      }
    }
    """
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://leetcode.com"
    }
    
    try:
        resp = await client.post(
            url,
            json={"query": query, "variables": {"username": username}},
            headers=headers,
            timeout=8
        )
        
        if resp.status_code != 200:
            logger.warning(f"LeetCode GraphQL returned status {resp.status_code} for {username}")
            return None
            
        data = resp.json()
        matched_user = data.get("data", {}).get("matchedUser")
        if not matched_user:
            logger.warning(f"LeetCode user {username} not found or query failed")
            return None
            
        # Parse solved count
        solved_count = 0
        difficulty_solved = {}
        submit_stats = matched_user.get("submitStatsGlobal", {})
        for ac in submit_stats.get("acSubmissionNum", []):
            diff = ac.get("difficulty")
            count = ac.get("count", 0)
            difficulty_solved[diff] = count
            if diff == "All":
                solved_count = count
                
        # Parse languages
        languages = []
        lang_count = matched_user.get("languageProblemCount", [])
        if lang_count:
            for lc in lang_count:
                lang = lc.get("languageName")
                count = lc.get("problemsSolved", 0)
                if count > 0:
                    # LeetCode language names normalize easily: "cpp" -> "C++", "python" -> "Python"
                    languages.append(_normalize_lc_language(lang))

        return {
            "username": username,
            "solved_count": solved_count,
            "difficulty_solved": difficulty_solved,
            "languages": list(filter(None, languages))
        }
    except Exception as e:
        logger.error(f"LeetCode GraphQL query failed for {username}: {e}")
        return None

def _normalize_lc_language(lang: str) -> str:
    lang_lower = lang.lower()
    if lang_lower == "cpp" or lang_lower == "c++":
        return "C++"
    if lang_lower == "python" or lang_lower == "python3":
        return "Python"
    if lang_lower == "java":
        return "Java"
    if lang_lower == "golang" or lang_lower == "go":
        return "Go"
    if lang_lower == "rust":
        return "Rust"
    if lang_lower == "javascript" or lang_lower == "js":
        return "JavaScript"
    if lang_lower == "typescript" or lang_lower == "ts":
        return "TypeScript"
    # Fallback to capitalized
    return lang.capitalize()

async def fetch_codechef_stats(client: httpx.AsyncClient, username: str) -> dict | None:
    """Fetch CodeChef profile stats by scraping public page HTML."""
    if not username:
        return None
        
    url = f"https://www.codechef.com/users/{username}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    
    try:
        resp = await client.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            logger.warning(f"CodeChef profile request returned status {resp.status_code} for {username}")
            return None
            
        html = resp.text
        import re

        # 1. Rating
        rating = None
        rating_match = re.search(r'<div class="rating-number">\s*([0-9]+)\s*</div>', html)
        if rating_match:
            rating = int(rating_match.group(1))

        # 2. Stars
        stars = None
        stars_container = re.search(r'<div class="rating-star">([\s\S]*?)</div>', html)
        if stars_container:
            star_html = stars_container.group(1)
            stars_count = star_html.count("&#9733;") + star_html.count("★")
            if stars_count > 0:
                stars = f"{stars_count}★"
            else:
                text_stars = re.search(r'([1-7])\s*★', star_html)
                if text_stars:
                    stars = f"{text_stars.group(1)}★"
        
        if not stars and rating:
            if rating >= 2500:
                stars = "7★"
            elif rating >= 2200:
                stars = "6★"
            elif rating >= 2000:
                stars = "5★"
            elif rating >= 1800:
                stars = "4★"
            elif rating >= 1600:
                stars = "3★"
            elif rating >= 1400:
                stars = "2★"
            else:
                stars = "1★"

        # 3. Global/Country Ranks
        global_rank = None
        country_rank = None
        rating_ranks = re.search(r'<div class="rating-ranks">([\s\S]*?)</div>', html)
        if rating_ranks:
            ranks_html = rating_ranks.group(1)
            gr_match = re.search(r'<strong>\s*([^<]+?)\s*</strong>\s*</a>\s*Global Rank', ranks_html)
            if gr_match:
                global_rank = gr_match.group(1).strip()
            cr_match = re.search(r'<strong>\s*([^<]+?)\s*</strong>\s*</a>\s*Country Rank', ranks_html)
            if cr_match:
                country_rank = cr_match.group(1).strip()

        # 4. Solved Count
        solved_count = 0
        solved_match = re.search(r'Total Problems Solved:\s*(\d+)', html)
        if solved_match:
            solved_count = int(solved_match.group(1))
        else:
            problems_section = re.search(r'<section class="rating-data-section problems-solved">([\s\S]*?)</section>', html)
            if problems_section:
                sect_html = problems_section.group(1)
                sect_h3s = re.findall(r'<h3>([^<]+)</h3>', sect_html)
                for h3 in sect_h3s:
                    match = re.search(r'\(([^)]+)\)', h3)
                    if match:
                        val = match.group(1).strip()
                        if val.isdigit():
                            solved_count += int(val)

        return {
            "username": username,
            "rating": rating,
            "stars": stars,
            "global_rank": global_rank,
            "country_rank": country_rank,
            "solved_count": solved_count
        }
    except Exception as e:
        logger.error(f"CodeChef analysis failed for {username}: {e}")
        return None

async def analyze_dsa(leetcode_username: str | None, codeforces_username: str | None, codechef_username: str | None, client: httpx.AsyncClient) -> dict:
    """Run DSA profile collections concurrently."""
    import asyncio
    
    tasks = []
    if leetcode_username:
        tasks.append(fetch_leetcode_stats(client, leetcode_username))
    else:
        tasks.append(asyncio.sleep(0, result=None))
        
    if codeforces_username:
        tasks.append(fetch_codeforces_stats(client, codeforces_username))
    else:
        tasks.append(asyncio.sleep(0, result=None))
        
    if codechef_username:
        tasks.append(fetch_codechef_stats(client, codechef_username))
    else:
        tasks.append(asyncio.sleep(0, result=None))
        
    lc_res, cf_res, cc_res = await asyncio.gather(*tasks)
    
    return {
        "leetcode": lc_res,
        "codeforces": cf_res,
        "codechef": cc_res
    }
