import csv
import requests
import datetime
import time
import os
import urllib.parse
import json
import re
import configparser

def load_config():
    """从配置文件加载配置"""
    config = configparser.ConfigParser()
    
    # 检查配置文件是否存在，如果不存在则创建默认配置
    if not os.path.exists('config.ini'):
        print("未找到配置文件，创建默认配置文件 'config.ini'")
        config['API'] = {
            'tmdb_api_key': '请输入你的API Key(API密钥)',
            'trakt_client_id': '请输入你的Trakt Client ID'  # 新增Trakt API配置
        }
        config['Files'] = {
            'input_csv': '请输入你的文件名.csv',
            'output_csv': 'bangumi_export.csv'
        }
        config['Settings'] = {
            'watch_status': '看过'  # 添加默认的观看状态设置
        }
        
        with open('config.ini', 'w', encoding='utf-8') as configfile:
            config.write(configfile)
    
    # 读取配置文件
    config.read('config.ini', encoding='utf-8')
    
    # 确保Settings部分存在
    if 'Settings' not in config:
        config['Settings'] = {}
    
    # 确保watch_status设置存在
    if 'watch_status' not in config['Settings']:
        config['Settings']['watch_status'] = '看过'
        with open('config.ini', 'w', encoding='utf-8') as configfile:
            config.write(configfile)
    
    return config

# 全局配置对象
CONFIG = load_config()

def get_trakt_data(trakt_id):
    """通过Trakt API获取影视数据"""
    # 从配置文件获取Trakt Client ID
    trakt_client_id = CONFIG['API'].get('trakt_client_id', '')
    
    if not trakt_client_id or trakt_client_id == '请输入你的Trakt Client ID':
        print("Trakt Client ID未配置，无法获取Trakt数据")
        return None
    
    url = f"https://api.trakt.tv/shows/{trakt_id}" if trakt_id else None
    
    # 如果无法确定类型（电影还是剧集），先尝试剧集，然后尝试电影
    if url:
        headers = {
            "Content-Type": "application/json",
            "trakt-api-version": "2",
            "trakt-api-key": trakt_client_id
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                show_data = response.json()
                print(f"成功获取剧集数据: {show_data.get('title')}")
                
                # 从Trakt获取TMDB ID
                tmdb_id = show_data.get("ids", {}).get("tmdb")
                if tmdb_id:
                    # 使用TMDB ID获取详细信息
                    return get_tmdb_details(tmdb_id, "tv")
                else:
                    print(f"Trakt剧集数据中没有TMDB ID")
            elif response.status_code == 404:
                # 尝试获取电影数据
                url = f"https://api.trakt.tv/movies/{trakt_id}"
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    movie_data = response.json()
                    print(f"成功获取电影数据: {movie_data.get('title')}")
                    
                    # 从Trakt获取TMDB ID
                    tmdb_id = movie_data.get("ids", {}).get("tmdb")
                    if tmdb_id:
                        # 使用TMDB ID获取详细信息
                        return get_tmdb_details(tmdb_id, "movie")
                    else:
                        print(f"Trakt电影数据中没有TMDB ID")
                else:
                    print(f"Trakt API请求失败: {response.status_code}")
            else:
                print(f"Trakt API请求失败: {response.status_code}")
        except Exception as e:
            print(f"Trakt API请求失败: {str(e)}")
    
    return None

def get_tmdb_data(imdb_id):
    """通过 TMDB API 获取影视数据"""
    # 从配置文件获取TMDB API密钥
    tmdb_api_key = CONFIG['API']['tmdb_api_key']
    url = f"https://api.themoviedb.org/3/find/{imdb_id}?api_key={tmdb_api_key}&external_source=imdb_id"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # TMDB的find接口会返回电影或电视剧的结果
            movie_results = data.get("movie_results", [])
            tv_results = data.get("tv_results", [])
            
            if movie_results:
                result = movie_results[0]
                tmdb_id = result.get("id")
                # 获取更详细的电影数据
                return get_tmdb_details(tmdb_id, "movie")
            elif tv_results:
                result = tv_results[0]
                tmdb_id = result.get("id")
                # 获取更详细的电视剧数据
                return get_tmdb_details(tmdb_id, "tv")
            else:
                print(f"在TMDB中找不到imdb ID为{imdb_id}的作品")
                return None
    except Exception as e:
        print(f"TMDB API请求失败: {str(e)}")
    
    return None

def get_tmdb_details(tmdb_id, media_type):
    """获取TMDB详细信息"""
    tmdb_api_key = CONFIG['API']['tmdb_api_key']
    url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}?api_key={tmdb_api_key}&append_to_response=release_dates,content_ratings"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            
            # 获取发布日期
            released = None
            if media_type == "movie":
                released = data.get("release_date")
            else:  # tv
                released = data.get("first_air_date")
            
            # 获取制作国家
            country = "unknown"
            country_name = "未知"
            production_countries = data.get("production_countries", [])
            if production_countries:
                country = production_countries[0].get("iso_3166_1", "unknown").lower()
                country_name = production_countries[0].get("name", "未知")
            
            # 获取年份
            year = None
            if released:
                year = int(released.split("-")[0])
            
            return {
                "title": data.get("title") if media_type == "movie" else data.get("name"),
                "released": released,
                "country": country,
                "country_name": country_name,
                "year": year,
                "tmdb_id": tmdb_id,
                "media_type": media_type,
                "imdb_id": data.get("imdb_id")
            }
    except Exception as e:
        print(f"获取TMDB详情失败: {str(e)}")
    
    return None

def get_japanese_title(tmdb_data):
    """通过TMDB API获取日文原名"""
    tmdb_id = tmdb_data.get("tmdb_id")
    media_type = tmdb_data.get("media_type")
    
    if not tmdb_id:
        print("没有找到TMDB ID，无法获取日文标题")
        return tmdb_data.get("title")
    
    # 使用TMDB API获取日文标题
    japanese_title = get_tmdb_japanese_title(tmdb_id, media_type)
    if japanese_title:
        print(f"从TMDB获取到日文标题: {japanese_title}")
        return japanese_title
    
    # 如果是日本作品但没找到日文标题，进行简单转换尝试
    if tmdb_data.get("country") == "jp":
        eng_title = tmdb_data.get("title", "")
        # 一些简单的英文→日文标题猜测规则
        if ":" in eng_title:
            base_title = eng_title.split(":")[0].strip()
            print(f"根据英文标题猜测日文标题基础部分: {base_title}")
            return base_title
    
    # 返回原始英文标题作为后备
    return tmdb_data.get("title")

def get_tmdb_japanese_title(tmdb_id, media_type):
    """从TMDB获取日文标题"""
    tmdb_api_key = CONFIG['API']['tmdb_api_key']
    
    url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}?api_key={tmdb_api_key}&language=ja"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # 尝试获取日文标题
            japanese_title = data.get("title") if media_type == "movie" else data.get("name")
            if japanese_title and is_japanese(japanese_title):
                return japanese_title
            
            # 如果主标题不是日文，检查alternative_titles
            alt_titles_url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}/alternative_titles?api_key={tmdb_api_key}"
            alt_response = requests.get(alt_titles_url, timeout=10)
            if alt_response.status_code == 200:
                alt_data = alt_response.json()
                titles_key = "titles" if media_type == "movie" else "results"
                for title_obj in alt_data.get(titles_key, []):
                    if title_obj.get("iso_3166_1") == "JP":
                        return title_obj.get("title") if media_type == "movie" else title_obj.get("name")
    except Exception as e:
        print(f"TMDB API请求失败: {str(e)}")
    
    return None

def is_japanese(text):
    """简单判断文本是否含有日文字符"""
    # 日文字符范围（平假名、片假名、汉字部分范围）
    japanese_pattern = re.compile(r'[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]')
    return bool(japanese_pattern.search(text))

def search_bangumi(title, japanese_title, released, year=None):
    """通过 Bangumi API 搜索匹配的条目，优先使用日文标题"""
    results = []
    
    # 1. 首先尝试使用日文标题搜索
    if japanese_title and japanese_title != title:
        encoded_jp_title = urllib.parse.quote(japanese_title)
        jp_results = _search_bangumi_api(encoded_jp_title)
        if jp_results:
            print(f"使用日文标题'{japanese_title}'搜索到 {len(jp_results)} 个结果")
            results.extend(jp_results)
        
        # 尝试日文标题拆分简化搜索
        if not jp_results and (japanese_title.find(':') > 0 or japanese_title.find('：') > 0 or 
                              japanese_title.find('-') > 0 or japanese_title.find('～') > 0 or
                              japanese_title.find('〜') > 0 or ' ' in japanese_title):
            # 处理日文常见的分隔符
            main_jp_title = japanese_title
            for sep in [':', '：', '-', '～', '〜']:
                if sep in main_jp_title:
                    main_jp_title = main_jp_title.split(sep)[0]
            
            # 单独处理空格，因为空格可能是标题本身的一部分
            # 只有当其他分隔符都不存在时，才考虑用空格分割
            if main_jp_title == japanese_title and ' ' in japanese_title:
                # 有些日文标题格式是"主标题 副标题"
                main_jp_title = japanese_title.split(' ')[0]
            
            main_jp_title = main_jp_title.strip()
            if main_jp_title != japanese_title:
                print(f"尝试使用简化日文标题: {main_jp_title}")
                encoded_simple_jp_title = urllib.parse.quote(main_jp_title)
                simple_jp_results = _search_bangumi_api(encoded_simple_jp_title)
                if simple_jp_results:
                    print(f"使用简化日文标题'{main_jp_title}'搜索到 {len(simple_jp_results)} 个结果")
                    results.extend(simple_jp_results)
    
    # 2. 然后使用英文标题搜索
    encoded_title = urllib.parse.quote(title)
    eng_results = _search_bangumi_api(encoded_title)
    if eng_results:
        print(f"使用英文标题'{title}'搜索到 {len(eng_results)} 个结果")
        results.extend(eng_results)
    
    # 3. 如果仍无结果，尝试英文标题拆分
    if not results and (title.find(':') > 0 or title.find('-') > 0 or ' ' in title):
        main_title = title
        for sep in [':', '-']:
            if sep in main_title:
                main_title = main_title.split(sep)[0]
        
        # 如果标题中有空格，且没有其他分隔符，考虑第一个空格前的部分
        if main_title == title and ' ' in title and len(title.split(' ')) > 1:
            # 避免过度简化短标题
            words = title.split(' ')
            if len(words) > 2:  # 至少有三个词的标题才考虑简化
                main_title = ' '.join(words[:2])  # 取前两个词
        
        main_title = main_title.strip()
        if main_title != title and len(main_title) > 3:  # 确保简化后的标题不会太短
            print(f"尝试使用简化英文标题: {main_title}")
            encoded_simple_title = urllib.parse.quote(main_title)
            simple_results = _search_bangumi_api(encoded_simple_title)
            if simple_results:
                print(f"使用简化英文标题'{main_title}'搜索到 {len(simple_results)} 个结果")
                results.extend(simple_results)
    
    # 处理搜索结果
    if results:
        return _process_bangumi_results(results, title, japanese_title, released, year)
    
    return None, None, None, None, 0.0  # 添加相似度分数作为返回值

def _search_bangumi_api(encoded_title):
    """调用Bangumi API进行搜索"""
    url = f"https://api.bgm.tv/search/subject/{encoded_title}?type=2,6&responseGroup=small"
    
    headers = {
        "User-Agent": "TMDBToBangumi/1.0",
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            # 检查响应内容是否为空
            if not response.text.strip():
                print(f"Bangumi API返回空响应，可能是API速率限制或搜索条件无效：{encoded_title}")
                return []
                
            try:
                data = response.json()
                
                # 根据返回结构提取结果列表
                if isinstance(data, dict) and "list" in data:
                    return data["list"]
                elif isinstance(data, list):
                    return data
                else:
                    print(f"Bangumi API返回了意外的数据结构：{data}")
                    return []
                    
            except json.JSONDecodeError as e:
                print(f"JSON解析错误: {str(e)}, 响应内容: {response.text[:100]}...")
                return []
        else:
            print(f"Bangumi API请求失败，状态码: {response.status_code}")
            return []
        
        # 避免API速率限制
        time.sleep(0.3)  # 增加间隔时间
        
    except requests.exceptions.Timeout:
        print(f"Bangumi API请求超时")
        time.sleep(2)  # 超时后增加更长的等待时间
        return []
    except Exception as e:
        print(f"Bangumi API请求出错: {str(e)}")
        return []
    
    return []

def _process_bangumi_results(results, title, japanese_title, released, year):
    """处理Bangumi搜索结果并找出最佳匹配"""
    best_match = None
    best_score = 0
    best_similarity = 0  # 保存最佳匹配的相似度
    
    for item in results:
        bgm_id = item.get("id")
        bgm_title = item.get("name", "")
        bgm_cn_title = item.get("name_cn", "")
        bgm_date = item.get("air_date", item.get("date", ""))
        
        print(f"评估条目: ID={bgm_id}, 标题={bgm_title}, 中文标题={bgm_cn_title}, 日期={bgm_date}")
        
        # 计算匹配分数
        score = 0
        
        # 1. 标题匹配分数
        en_similarity = check_title_similarity(title, bgm_title, bgm_cn_title)
        jp_similarity = 0
        if japanese_title:
            jp_similarity = check_title_similarity(japanese_title, bgm_title, bgm_cn_title)
        
        # 取最高的标题相似度
        title_similarity = max(en_similarity, jp_similarity)
        score += title_similarity * 5  # 标题相似度权重加大
        
        # 2. 日期匹配分数
        if bgm_date and released:
            date_score = calculate_date_score(released, bgm_date)
            score += date_score
        
        # 3. 年份匹配额外加分
        if year and bgm_date and len(bgm_date) >= 4 and bgm_date[:4] == str(year):
            score += 2
        
        print(f"条目 {bgm_id} 的匹配分数: {score} (标题相似度: {title_similarity})")
        
        # 更新最佳匹配
        if score > best_score:
            best_score = score
            best_similarity = title_similarity  # 保存相似度
            best_match = item
    
    # 如果最佳分数达到阈值
    if best_score >= 2.5:  # 调整阈值可以控制匹配的严格程度
        print(f"找到最佳匹配: ID={best_match.get('id')}, 分数={best_score}")
        return (
            best_match.get("id"),
            best_match.get("name"),
            best_match.get("name_cn", ""),
            best_match.get("air_date", best_match.get("date", "")),  # 返回Bangumi的放送日期
            best_similarity  # 返回最高标题相似度
        )
    
    print(f"未找到足够可信的匹配项 (最高分数: {best_score})")
    return None, None, None, None, 0.0

def check_title_similarity(source_title, bgm_title, bgm_cn_title):
    """检查标题相似度"""
    from difflib import SequenceMatcher
    
    # 如果任一标题为空，返回0
    if not source_title or (not bgm_title and not bgm_cn_title):
        return 0
    
    # 计算与英文标题的相似度
    similarity1 = SequenceMatcher(None, source_title.lower(), bgm_title.lower()).ratio()
    
    # 计算与中文标题的相似度（如果有）
    similarity2 = 0
    if bgm_cn_title:
        similarity2 = SequenceMatcher(None, source_title.lower(), bgm_cn_title.lower()).ratio()
    
    # 返回最高相似度
    return max(similarity1, similarity2)

def calculate_date_score(tmdb_date, bgm_date):
    """计算日期匹配分数，日期越接近分数越高"""
    try:
        tmdb_dt = datetime.datetime.strptime(tmdb_date, "%Y-%m-%d")
        bgm_dt = datetime.datetime.strptime(bgm_date, "%Y-%m-%d")
        diff = abs((tmdb_dt - bgm_dt).days)
        
        # 完全匹配得3分
        if diff == 0:
            return 3
        # 1周内得2分
        elif diff <= 7:
            return 2
        # 1个月内得1分
        elif diff <= 30:
            return 1
        # 同一年得0.5分
        elif tmdb_dt.year == bgm_dt.year:
            return 0.5
        # 相差一年得0.2分
        elif abs(tmdb_dt.year - bgm_dt.year) == 1:
            return 0.2
        # 其他情况得0分
        else:
            return 0
    except:
        return 0

def get_bangumi_details(bgm_id):
    """获取Bangumi条目详细信息"""
    url = f"https://api.bgm.tv/subject/{bgm_id}?responseGroup=large"
    
    headers = {
        "User-Agent": "TMDBToBangumi/1.0",
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return data
        
        # 避免API速率限制
        time.sleep(0.3)
    except Exception as e:
        print(f"获取Bangumi详情失败: {str(e)}")
    
    return None

def convert_csv():
    """转换CSV文件为Bangumi导入格式，实时写入结果"""
    # 从配置文件读取输入输出文件名
    input_csv = CONFIG['Files']['input_csv']
    output_csv = CONFIG['Files']['output_csv']
    
    # 从配置文件读取自定义的观看状态
    watch_status = CONFIG['Settings']['watch_status']
    print(f"使用自定义观看状态: {watch_status}")
    
    # 创建日志文件名
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    success_log = f"success_log_{timestamp}.csv"
    failure_log = f"failure_log_{timestamp}.csv"
    
    if not os.path.exists(input_csv):
        print(f"文件 {input_csv} 不存在！")
        input("按任意键退出...")
        return
    
    # 首先获取要处理的总条目数，用于进度跟踪
    try:
        with open(input_csv, newline='', encoding='utf-8') as count_file:
            total_items = sum(1 for _ in csv.DictReader(count_file))
        print(f"共找到 {total_items} 条记录需要处理")
    except Exception as e:
        print(f"读取CSV文件出错: {str(e)}")
        total_items = 0
    
    # 初始化输出文件，写入表头
    with open(output_csv, 'w', newline='', encoding='utf-8') as outfile:
        writer = csv.writer(outfile)
        # 修改CSV表头，增加制作地区字段
        writer.writerow(["ID", "类型", "中文", "日文", "放送", "排名", "评分", "话数", "看到", "状态", "标签", "我的评价", "我的简评", "私密", "更新时间", "制作地区"])
    
    # 初始化成功日志文件
    with open(success_log, 'w', newline='', encoding='utf-8') as success_file:
        success_writer = csv.writer(success_file)
        success_writer.writerow(["原IMDB ID", "原标题", "匹配Bangumi ID", "匹配日文标题", "匹配中文标题", "相似度", "制作地区", "TMDB类型"])
    
    # 初始化失败日志文件
    with open(failure_log, 'w', newline='', encoding='utf-8') as failure_file:
        failure_writer = csv.writer(failure_file)
        failure_writer.writerow(["原IMDB ID", "原标题", "失败原因", "制作地区", "TMDB类型"])
    
    # 读取输入CSV并逐条处理
    with open(input_csv, newline='', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        
        processed_items = 0
        successful_matches = 0
        
        for row in reader:
            processed_items += 1
            print(f"\n处理进度: [{processed_items}/{total_items}]")
            
            try:
                imdb_id = row.get("imdb", "")  # 使用"imdb"字段
                trakt_id = row.get("trakt", "")  # 使用"trakt"字段
                watched_at = row.get("watched_at", "")  # 使用"watched_at"字段
                csv_title = row.get("title", "")  # 使用CSV中的标题作为备选
                
                tmdb_data = None
                media_type = "unknown"
                country_name = "未知"
                failure_reason = ""
                
                # 首先检查是否有IMDB ID
                if imdb_id and imdb_id.strip():
                    print(f"正在使用IMDB ID处理: {imdb_id} (标题: {csv_title})")
                    # 使用TMDB API获取数据
                    tmdb_data = get_tmdb_data(imdb_id)
                # 如果没有IMDB ID但有Trakt ID，则使用Trakt ID搜索
                elif trakt_id and trakt_id.strip():
                    print(f"IMDB ID为空，尝试使用Trakt ID: {trakt_id} (标题: {csv_title})")
                    tmdb_data = get_trakt_data(trakt_id)
                
                if not tmdb_data:
                    failure_reason = "未找到TMDB数据"
                    print(f"未找到作品的TMDB数据，尝试使用CSV中的标题。")
                    # 创建一个简单的数据结构作为备用
                    tmdb_data = {
                        "title": csv_title,
                        "released": None,
                        "country": "unknown",
                        "country_name": "未知",
                        "year": None,
                        "tmdb_id": None,
                        "media_type": "unknown"
                    }
                
                # 保存类型和地区信息用于日志
                media_type = tmdb_data["media_type"]
                country_name = tmdb_data["country_name"]
                
                # 获取日文标题
                japanese_title = get_japanese_title(tmdb_data)
                print(f"获取到的标题信息: 英文='{tmdb_data['title']}', 日文='{japanese_title}', 制作地区='{tmdb_data['country_name']}'")
                
                # 搜索Bangumi
                bangumi_id, bgm_jp_title, bgm_cn_title, bgm_air_date, similarity = search_bangumi(
                    tmdb_data["title"],
                    japanese_title,
                    tmdb_data["released"],
                    tmdb_data["year"]
                )
                
                if not bangumi_id:
                    print(f"未找到 Bangumi 匹配项: {tmdb_data['title']}，尝试使用CSV中的标题。")
                    # 尝试使用CSV中的标题进行搜索
                    if csv_title != tmdb_data["title"]:
                        bangumi_id, bgm_jp_title, bgm_cn_title, bgm_air_date, similarity = search_bangumi(
                            csv_title,
                            None,
                            tmdb_data["released"],
                            tmdb_data["year"]
                        )
                

                if not bangumi_id:
                    failure_reason = failure_reason or "未找到Bangumi匹配项"
                    print(f"仍未找到 Bangumi 匹配项，记录失败日志。")
                    
                    # 记录失败日志
                    with open(failure_log, 'a', newline='', encoding='utf-8') as failure_file:
                        failure_writer = csv.writer(failure_file)
                        failure_writer.writerow([imdb_id, csv_title, failure_reason, country_name, media_type])
                    
                    continue
                
                # 如果没有获取到Bangumi的放送日期，尝试获取更详细的信息
                if not bgm_air_date:
                    print("未从搜索结果获取到Bangumi放送日期，尝试获取详细信息...")
                    bgm_details = get_bangumi_details(bangumi_id)
                    if bgm_details:
                        bgm_air_date = bgm_details.get("air_date", "")
                        print(f"从Bangumi详情获取到放送日期: {bgm_air_date}")
                
                # 如果仍然没有Bangumi放送日期，则使用TMDB日期作为备选
                if not bgm_air_date:
                    print("未获取到Bangumi放送日期，使用TMDB日期作为备选")
                    bgm_air_date = tmdb_data["released"]
                
                successful_matches += 1
                
                # 记录成功日志
                with open(success_log, 'a', newline='', encoding='utf-8') as success_file:
                    success_writer = csv.writer(success_file)
                    success_writer.writerow([
                        imdb_id, 
                        csv_title, 
                        bangumi_id, 
                        bgm_jp_title, 
                        bgm_cn_title, 
                        f"{similarity:.3f}", 
                        country_name, 
                        media_type
                    ])
                
                # 判断类型：如果是日本作品，默认为"动画"，否则为"电影"或"剧集"
                if tmdb_data["country"] == "jp":
                    category = "动画"
                else:
                    category = "剧集" if tmdb_data.get("media_type") == "tv" else "电影"
                
                # 格式化观看日期 (如果需要转换格式)
                try:
                    # 尝试解析ISO格式的日期时间
                    watched_datetime = datetime.datetime.fromisoformat(watched_at.replace("Z", "+00:00"))
                    formatted_watched_at = watched_datetime.strftime("%Y-%m-%d")
                except:
                    formatted_watched_at = watched_at
                
                # 实时写入匹配结果到输出文件
                with open(output_csv, 'a', newline='', encoding='utf-8') as outfile:
                    writer = csv.writer(outfile)
                    writer.writerow([bangumi_id, category, bgm_cn_title, bgm_jp_title, bgm_air_date, "", "", "", "", watch_status, "", "", "", "", formatted_watched_at, tmdb_data["country_name"]])
                
                print(f"成功转换并写入: {csv_title} -> Bangumi ID: {bangumi_id}, 放送日期: {bgm_air_date}, 制作地区: {tmdb_data['country_name']}")
                
                # 显示当前进度和匹配率
                current_match_rate = (successful_matches / processed_items * 100)
                print(f"当前匹配率: {current_match_rate:.2f}% ({successful_matches}/{processed_items})")
                
                time.sleep(0.3)  # 避免 API 速率限制
                
            except Exception as e:
                print(f"转换时出错: {str(e)}")
                
                # 记录失败日志
                with open(failure_log, 'a', newline='', encoding='utf-8') as failure_file:
                    failure_writer = csv.writer(failure_file)
                    failure_writer.writerow([
                        row.get('imdb', 'unknown'), 
                        row.get('title', 'unknown'), 
                        f"处理异常: {str(e)}", 
                        row.get('country_name', '未知'), 
                        row.get('media_type', 'unknown')
                    ])
                
                # 记录错误，继续处理下一条
                with open('error_log.txt', 'a', encoding='utf-8') as error_log:
                    error_log.write(f"处理失败 [{processed_items}/{total_items}]: IMDB ID={row.get('imdb', 'unknown')}, 标题={row.get('title', 'unknown')}, 错误: {str(e)}\n")
                    import traceback
                    error_log.write(traceback.format_exc() + "\n\n")
    
# 完成后的总结
    final_match_rate = (successful_matches / total_items * 100) if total_items > 0 else 0
    print(f"\n处理完成！")
    print(f"- 总条目数: {total_items}")
    print(f"- 成功匹配: {successful_matches}")
    print(f"- 失败条目: {total_items - successful_matches}")
    print(f"- 最终匹配率: {final_match_rate:.2f}%")
    print(f"\n输出文件:")
    print(f"- Bangumi导入CSV: {output_csv}")
    print(f"- 成功匹配日志: {success_log}")
    print(f"- 失败匹配日志: {failure_log}")
    
    # 打开结果文件以便用户查看
    try:
        if os.name == 'nt':  # Windows
            os.system(f'start "" "{output_csv}"')
        elif os.name == 'posix':  # macOS 和 Linux
            if os.system('which open > /dev/null') == 0:  # macOS
                os.system(f'open "{output_csv}"')
            else:  # Linux
                os.system(f'xdg-open "{output_csv}" 2>/dev/null')
    except:
        pass
    
    print("\n处理完成。按任意键退出...")
    input()

if __name__ == "__main__":
    print("欢迎使用 Trakt-to-Bangumi 转换工具 2.0")
    print("本工具将把 Trakt 导出的观看记录转换为 Bangumi 可导入格式")
    print("确保已在 config.ini 文件中设置了正确的 TMDB API Key 和文件路径")
    print(f"当前观看状态设定为: {CONFIG['Settings']['watch_status']}")
    print("可用的观看状态: 想看、看过、在看、搁置、抛弃")
    print("-" * 60)
    
    convert_csv()