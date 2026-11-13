from datetime import datetime
from itertools import combinations
import json
import os
import requests

# ==========================================
# 1. 건물별 호실 전용면적 기준표 (여기에 건물 데이터를 추가하면 자동 매칭됩니다)
# ==========================================
BUILDING_DB = {
    "배곧프라자": {
        "6": {
            "601호": 115.50,
            "602호": 115.50,
            "603호": 201.60,
            "604호": 121.26,
            "605호": 121.26,
            "606호": 201.60,
        }
    },
    "베니스": {
        "1": {"에스-11": 39.24, "에스-12": 39.24, "에스-15": 39.24},
        "2": {
            "서영베니스스퀘어 259호": 50.70,
            "서영베니스스퀘어 260호": 50.70,
            "서영베니스스퀘어 261호": 50.70,
            "서영베니스스퀘어 262호": 50.70,
            "서영베니스스퀘어 275호": 33.71,
            "서영베니스스퀘어 276호": 33.71,
            "서영베니스스퀘어 277호": 33.71,
            "서영베니스스퀘어 278호": 33.71,
        },
    },
    "SK월드프라자": {"1": {"102": 44.00, "103": 44.00, "107": 44.00}},
}

# ==========================================
# 2. 환경변수 및 설정
# ==========================================
REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY")
REFRESH_TOKEN = os.environ.get("KAKAO_REFRESH_TOKEN")
WEB_PAGE_URL = os.environ.get(
    "WEB_PAGE_URL", "https://m.land.naver.com"
)  # 깃허브 페이지 주소


# ==========================================
# 3. 호실 후보 및 합산 범위 자동 계산 엔진
# ==========================================
def match_rooms_and_combinations(
    building_name, floor_str, target_area_str, desc
):
  try:
    target_area = float(target_area_str)
  except (ValueError, TypeError):
    return desc or "면적 정보 없음"

  # 층 정보에서 숫자만 추출 (예: "6/10" -> "6")
  floor = str(floor_str).split("/")[0].strip()

  # 기준표에서 일치하는 건물명 찾기
  matched_bldg = None
  for b_key in BUILDING_DB:
    if b_key in building_name or building_name in b_key:
      matched_bldg = b_key
      break

  if not matched_bldg or floor not in BUILDING_DB[matched_bldg]:
    return f"{building_name} ({desc[:35]})" if desc else f"{building_name} 미확정"

  rooms = BUILDING_DB[matched_bldg][floor]
  tolerance = 0.25  # 오차 허용 범위 (±0.25㎡)

  # ① 단일 호실 일치 후보 탐색
  single_matches = []
  for r_name, r_area in rooms.items():
    if abs(r_area - target_area) <= tolerance:
      single_matches.append(f"{matched_bldg} {r_name}")

  if single_matches:
    return " | ".join(single_matches)

  # ② 2개 ~ 3개 호실 합산 조합 탐색
  combo_matches = []
  room_items = list(rooms.items())
  for r_count in (2, 3):
    for combo in combinations(room_items, r_count):
      sum_area = round(sum(x[1] for x in combo), 2)
      diff = round(abs(sum_area - target_area), 2)
      if diff <= tolerance:
        names = " + ".join(x[0] for x in combo)
        areas = " + ".join(str(x[1]) for x in combo)
        combo_matches.append(
            f"{matched_bldg} {names} ({areas} = {sum_area}㎡, 차이 {diff:.2f}㎡)"
        )

  if combo_matches:
    return "합산 추정: " + " | ".join(combo_matches)

  return (
      f"미확정 ({desc[:30]})"
      if desc
      else f"{matched_bldg} {floor}층 후보 없음"
  )


# ==========================================
# 4. 네이버 부동산 수집기
# ==========================================
def get_naver_land_articles(cortar_no="4139013200", rlet_tp_cd="SG", page=1):
  url = "https://m.land.naver.com/cluster/ajax/articleList"
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
          " like Gecko) Chrome/124.0.0.0 Safari/537.36"
      ),
      "Referer": "https://m.land.naver.com/",
  }
  params = {
      "cortarNo": cortar_no,
      "rletTpCd": rlet_tp_cd,  # SG: 상가, SMS: 사무실
      "tradTpCd": "A1:B1:B2",
      "page": page,
      "sort": "dates",
  }
  res = requests.get(url, headers=headers, params=params, timeout=10)
  return res.json().get("body", []) if res.status_code == 200 else []


# ==========================================
# 5. HTML 웹페이지(전체 매물표) 생성기
# ==========================================
def build_html_page(articles, today_str):
  articles_json = json.dumps(articles, ensure_ascii=False)
  html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{today_str} 확인 매물 · 광고 금액표</title>
    <style>
        body {{ font-family: 'Malgun Gothic', -apple-system, sans-serif; margin: 16px; background: #fff; color: #222; }}
        h1 {{ font-size: 20px; margin-bottom: 10px; }}
        .badges {{ margin-bottom: 10px; }}
        .badge-rent {{ background: #b8e994; padding: 4px 10px; border-radius: 4px; font-weight: bold; font-size: 12px; margin-right: 5px; }}
        .badge-sale {{ background: #82ccdd; padding: 4px 10px; border-radius: 4px; font-weight: bold; font-size: 12px; }}
        .desc {{ font-size: 12px; color: #666; line-height: 1.5; margin-bottom: 15px; }}
        .controls {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 15px; }}
        input[type="text"] {{ padding: 8px 10px; border: 1px solid #ccc; border-radius: 4px; width: 240px; font-size: 13px; }}
        select {{ padding: 8px 10px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; }}
        .count-text {{ font-weight: bold; font-size: 13px; }}
        .table-wrap {{ overflow-x: auto; -webkit-overflow-scrolling: touch; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; min-width: 950px; }}
        th {{ background: #1e3746; color: #fff; padding: 10px 8px; text-align: left; white-space: nowrap; }}
        td {{ padding: 9px 8px; border-bottom: 1px solid #e0e0e0; line-height: 1.4; }}
        tr.rent {{ background-color: #eef9e6; }}
        tr.sale {{ background-color: #e6f4fa; }}
        .price {{ font-weight: bold; font-size: 13.5px; white-space: nowrap; }}
        .building {{ font-weight: bold; white-space: nowrap; }}
        .room-col {{ max-width: 380px; word-break: keep-all; }}
        a.art-link {{ color: #0984e3; text-decoration: underline; }}
    </style>
</head>
<body>
    <h1>{today_str} 확인 매물 · 광고 금액표</h1>
    <div class="badges">
        <span class="badge-rent">월세 · 연두색</span>
        <span class="badge-sale">매매 · 파란색</span>
    </div>
    <div class="desc">
        수집 당시 네이버 광고 금액입니다. 월세는 보증금/월세 순서이며 단위는 만원입니다. 확인일은 최초 등록일과 다를 수 있습니다.<br>
        호실은 추정 후보입니다. 여러 후보·합산 후보는 한 광고 행에 함께 표시하며, 합산 금액은 전체 매물 금액입니다.
    </div>
    <div class="controls">
        <input type="text" id="searchInput" placeholder="건물·호실·부동산·매물번호 검색" onkeyup="filterTable()">
        <select id="typeFilter" onchange="filterTable()">
            <option value="ALL">매매·월세 전체</option>
            <option value="월세">월세만 보기</option>
            <option value="매매">매매만 보기</option>
        </select>
        <span class="count-text" id="countDisplay">0건 / 전체 0건</span>
    </div>
    <div class="table-wrap">
        <table>
            <thead>
                <tr>
                    <th>건물</th>
                    <th>층</th>
                    <th>호실 후보·합산 범위</th>
                    <th>거래</th>
                    <th>광고 금액</th>
                    <th>전용 ㎡</th>
                    <th>확인일</th>
                    <th>광고 등록 부동산</th>
                    <th>매물번호</th>
                </tr>
            </thead>
            <tbody id="tableBody"></tbody>
        </table>
    </div>
    <script>
        const rawData = {articles_json};
        function renderTable(data) {{
            const tbody = document.getElementById('tableBody');
            tbody.innerHTML = '';
            data.forEach(row => {{
                const tr = document.createElement('tr');
                tr.className = row.trade_type === '월세' ? 'rent' : 'sale';
                tr.innerHTML = `
                    <td class="building">${{row.building}}</td>
                    <td>${{row.floor}}</td>
                    <td class="room-col">${{row.room_info}}</td>
                    <td>${{row.trade_type}}</td>
                    <td class="price">${{row.price}}</td>
                    <td>${{row.area}}</td>
                    <td>${{row.confirm_date}}</td>
                    <td>${{row.realtor}}</td>
                    <td><a class="art-link" href="https://m.land.naver.com/article/info/${{row.article_no}}" target="_blank">${{row.article_no}}</a></td>
                `;
                tbody.appendChild(tr);
            }});
            document.getElementById('countDisplay').innerText = `${{data.length}}건 / 전체 ${{rawData.length}}건`;
        }}
        function filterTable() {{
            const keyword = document.getElementById('searchInput').value.toLowerCase();
            const typeVal = document.getElementById('typeFilter').value;
            const filtered = rawData.filter(item => {{
                const matchType = (typeVal === 'ALL') || (item.trade_type === typeVal);
                const searchStr = `${{item.building}} ${{item.room_info}} ${{item.realtor}} ${{item.article_no}}`.toLowerCase();
                return matchType && searchStr.includes(keyword);
            }});
            renderTable(filtered);
        }}
        renderTable(rawData);
    </script>
</body>
</html>"""
  with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)


# ==========================================
# 6. 카카오톡 토큰 갱신 및 발송기
# ==========================================
def send_kakao_notification(today_str, total_count, rent_count, sale_count):
  if not REST_API_KEY or not REFRESH_TOKEN:
    print("카카오 API 키가 설정되지 않아 카톡 발송을 건너뜁니다.")
    return

  # 새 Access Token 발급
  token_res = requests.post(
      "https://kauth.kakao.com/oauth/token",
      data={
          "grant_type": "refresh_token",
          "client_id": REST_API_KEY,
          "refresh_token": REFRESH_TOKEN,
      },
  ).json()

  access_token = token_res.get("access_token")
  if not access_token:
    print("카카오 토큰 갱신 실패:", token_res)
    return

  msg = (
      f"🏢 [{today_str} 확인 매물 업데이트]\n\n"
      f"• 전체 수집: {total_count}건\n"
      f"• 월세: {rent_count}건 / 매매: {sale_count}건\n\n"
      "아래 버튼을 눌러 전체 매물표와 호실 합산 내역을 확인하세요."
  )

  template = {
      "object_type": "text",
      "text": msg,
      "link": {"web_url": WEB_PAGE_URL, "mobile_web_url": WEB_PAGE_URL},
      "button_title": "전체 매물·합산표 열기",
  }

  res = requests.post(
      "https://kapi.kakao.com/v2/api/talk/memo/default/send",
      headers={"Authorization": f"Bearer {access_token}"},
      data={"template_object": json.dumps(template, ensure_ascii=False)},
  )
  print("카카오톡 발송 완료:", res.status_code)


# ==========================================
# 7. 메인 통합 실행 함수
# ==========================================
def main():
  target_cortar_no = "4139013200"  # 시흥시 배곧동 법정동 코드
  raw_articles = []

  for page in range(1, 8):
    items = get_naver_land_articles(cortar_no=target_cortar_no, page=page)
    if not items:
      break
    for item in items:
      trad_type = item.get("tradTpNm", "")
      price = (
          f"{item.get('prc', 0):,}/{item.get('rentPrc', 0):,}"
          if trad_type == "월세"
          else item.get("dealOrWarrPrc", "")
      )
      room_info = match_rooms_and_combinations(
          item.get("atclNm", ""),
          item.get("flrInfo", ""),
          item.get("spc2", ""),
          item.get("atclFtrDesc", ""),
      )
      raw_articles.append({
          "building": item.get("atclNm", ""),
          "floor": str(item.get("flrInfo", "")).split("/")[0],
          "room_info": room_info,
          "trade_type": trad_type,
          "price": price,
          "area": item.get("spc2", ""),
          "confirm_date": item.get("cfmYmd", ""),
          "realtor": item.get("rltrNm", ""),
          "article_no": item.get("atclNo", ""),
      })

  # 중복 제거
  seen = set()
  articles = []
  for a in raw_articles:
    if a["article_no"] not in seen:
      seen.add(a["article_no"])
      articles.append(a)

  today_str = datetime.now().strftime("%Y-%m-%d")

  # 1) 웹페이지 생성
  build_html_page(articles, today_str)

  # 2) 카카오톡 알림 발송
  rent_cnt = sum(1 for a in articles if a["trade_type"] == "월세")
  sale_cnt = sum(1 for a in articles if a["trade_type"] == "매매")
  send_kakao_notification(today_str, len(articles), rent_cnt, sale_cnt)


if __name__ == "__main__":
  main()
