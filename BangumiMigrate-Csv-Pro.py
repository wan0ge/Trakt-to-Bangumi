import requests
import pandas as pd
import time
import logging
from concurrent.futures import ThreadPoolExecutor, wait
import re
import os
import configparser
import sys

# 设置日志级别
logging.basicConfig(level=logging.INFO)

# 读取配置文件
def load_config():
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')
    
    if not os.path.exists(config_path):
        logging.error(f"配置文件不存在: {config_path}")
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    
    config.read(config_path, encoding='utf-8')
    return config

def map_status_to_type(status):
    # 根据状态映射到对应的 type，这里需要根据实际情况进行调整
    if "想" in status:
        return 1
    elif "读过" in status or "看过" in status or "玩过" in status or "听过" in status:
        return 2
    elif "在读" in status or "在看" in status or "在玩" in status or "在听" in status:
        return 3
    elif "搁置" in status:
        return 4
    elif "抛弃" in status:
        return 5
    else:
        return 0  # 未知状态

def make_request(session, url, method='GET', data=None, access_token=None):
    base_headers = {
        'accept': '*/*',
        'Content-Type': 'application/json',
        'User-Agent': 'Adachi/BangumiMigrate(https://github.com/Adachi-Git/BangumiMigrate)',
        'Authorization': f'Bearer {access_token}'
    }

    try:
        response = session.request(method, url, headers=base_headers, json=data)
        response.raise_for_status()  # 检查请求是否成功

        # 记录日志
        logging.info(f"{method} request to {url} - Status Code: {response.status_code}")
        logging.debug("Request Headers:")
        logging.debug(base_headers)
        return response
        
    except requests.exceptions.RequestException as e:
        # 处理请求失败的情况，例如重试等
        logging.error(f"{method} request to {url} failed: {e}")
        return None

def get_subject_info(session, subject_id, access_token):
    """获取条目信息，包括总集数"""
    try:
        subject_url = f'https://api.bgm.tv/v0/subjects/{subject_id}'
        response = make_request(session, subject_url, method='GET', access_token=access_token)
        
        if response:
            subject_data = response.json()
            # 如果存在eps字段且不为空，返回总集数
            if 'total_episodes' in subject_data and subject_data['total_episodes'] is not None and subject_data['total_episodes'] > 0:
                return subject_data['total_episodes']
        
        # 如果无法获取或没有总集数信息，返回0
        return 0
        
    except Exception as e:
        logging.error(f"获取条目 {subject_id} 信息时出错: {e}")
        return 0

def mark_episode_watched(session, episode_id, access_token):
    """标记单个剧集为看过"""
    try:
        # 构建正确的 URL，对单集进行标记
        ep_url = f'https://api.bgm.tv/ep/{episode_id}/status/watched'
        
        # 发送请求标记剧集为看过
        response = make_request(session, ep_url, method='POST', access_token=access_token)
        
        if response:
            logging.info(f"剧集 {episode_id} 已成功标记为看过")
            return True
        else:
            logging.error(f"标记剧集 {episode_id} 失败")
            return False
    
    except Exception as e:
        logging.error(f"标记剧集 {episode_id} 时出错: {e}")
        return False

def update_progress(session, subject_id, eps_num, access_token, status_type, auto_complete=False):
    """设置条目的观看进度"""
    try:
        # 增加等待时间，确保收藏操作已完成
        time.sleep(3)
        
        logging.info(f"更新条目 {subject_id} 进度为第 {eps_num} 集")
        
        # 直接使用 progress API 更新进度
        progress_url = f'https://api.bgm.tv/subject/{subject_id}/update/watched_eps'
        
        # 这里使用表单数据而不是 JSON
        form_data = {'watched_eps': eps_num}
        
        # 调整 make_request 函数来发送表单数据
        headers = {
            'accept': '*/*',
            'User-Agent': 'wan0ge/Trakt-to-Bangumi(https://github.com/wan0ge/Trakt-to-Bangumi)',
            'Authorization': f'Bearer {access_token}'
        }
        
        try:
            # 使用表单数据发送请求
            response = session.post(progress_url, headers=headers, data=form_data)
            response.raise_for_status()
            
            logging.info(f"POST request to {progress_url} - Status Code: {response.status_code}")
            
            if response.status_code in [200, 201, 202, 204]:
                logging.info(f"条目 {subject_id} 已成功更新进度为看到第 {eps_num} 集")
                return True
            else:
                logging.error(f"更新条目 {subject_id} 进度失败，状态码: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logging.error(f"POST request to {progress_url} failed: {e}")
            return False
                
    except Exception as e:
        logging.error(f"更新条目 {subject_id} 的进度失败: {e}")
        return False

def process_row(row, api_url, wait_time, access_token, auto_complete=False):
    # 获取 'ID'、'状态'、'评分'、'我的简评'、'私密' 和 '标签' 列的值
    collection_id = row.ID
    status = row.状态
    rate = row.我的评价 if hasattr(row, '我的评价') else None
    comment = row.我的简评 if hasattr(row, '我的简评') else None
    private = row.私密 if hasattr(row, '私密') else None
    tags = row.标签.split() if (hasattr(row, '标签') and not pd.isna(row.标签)) else []
    
    # 获取进度信息
    watched_eps = 0
    total_eps = 0
    
    if hasattr(row, '看到') and not pd.isna(row.看到):
        watched_eps = int(row.看到)
    
    if hasattr(row, '话数') and not pd.isna(row.话数):
        try:
            total_eps = int(row.话数)
        except (ValueError, TypeError):
            # 处理非数字或特殊格式的情况
            total_eps = 0

    # 根据状态映射到对应的 type
    type_value = map_status_to_type(status)

    # 动态生成请求的 URL
    url = f'{api_url}{collection_id}'

    # 处理评论部分，去除不可见字符
    if comment is not None and isinstance(comment, str):
        comment = re.sub(r'[\x00-\x1F\x7F-\x9F\u200B-\u200F\u2028-\u202F\u2060-\u206F]', '', comment)
        
    # 准备请求体数据
    data = {
        "type": type_value,
        "rate": int(float(rate)) if (rate is not None and not pd.isna(rate) and rate != '') else 0,
        "comment": str(comment).strip() if (comment is not None and not pd.isna(comment)) else "",
        "private": bool(private) if (private is not None and not pd.isna(private)) else False,
        "tags": [tag.strip() for tag in tags] if tags else []
    }

    # 发送收藏请求
    with requests.Session() as session:
        collection_response = make_request(session, url, method='POST', data=data, access_token=access_token)
        
        # 处理进度
        if collection_response:
            eps_to_mark = 0
            
            # 修复: 根据auto_complete和type_value状态确定正确的标记策略
            # 如果是已完成状态("看过"等)且设置了自动标满进度
            if type_value == 2 and auto_complete:
                # 优先使用CSV中的总集数
                if total_eps > 0:
                    eps_to_mark = total_eps
                else:
                    # 如果CSV中没有总集数，则从API获取条目信息
                    api_total_eps = get_subject_info(session, collection_id, access_token)
                    if api_total_eps > 0:
                        eps_to_mark = api_total_eps
                        logging.info(f"条目 {collection_id} 从API获取总集数: {api_total_eps}")
                    elif watched_eps > 0:  # 如果API也获取不到，但有看到的集数，则使用看到的集数
                        eps_to_mark = watched_eps
                    else:
                        logging.warning(f"条目 {collection_id} 无法获取总集数，也没有'看到'数据，不更新进度")
            # 否则使用用户提供的观看进度
            elif watched_eps > 0:
                eps_to_mark = watched_eps
                
            # 只有当有明确的进度需要设置时才更新进度
            if eps_to_mark > 0:
                # 等待一段时间再更新进度
                time.sleep(2)
                # 更新进度
                update_progress(session, collection_id, eps_to_mark, access_token, type_value, auto_complete)

    # 等待一定时间
    time.sleep(wait_time)

def main():
    try:
        # 读取配置
        config = load_config()
        
        # 检查BangumiMigrate部分是否存在
        if 'BangumiMigrate' not in config:
            logging.error("配置文件中缺少[BangumiMigrate]部分")
            return
        
        # 获取配置项
        bangumi_access_token = config.get('BangumiMigrate', 'access_token')
        bangumi_input_csv = config.get('BangumiMigrate', 'input_csv')
        wait_time = config.getint('BangumiMigrate', 'wait_time', fallback=5)
        # 新增自动标满进度的配置项
        auto_complete = config.getboolean('BangumiMigrate', 'auto_complete', fallback=False)
        
        # API URL常量
        API_URL = 'https://api.bgm.tv/v0/users/-/collections/'
        
        # 检查配置
        if bangumi_access_token == '请输入你的Bangumi访问令牌':
            logging.error("请在config.ini的[BangumiMigrate]部分设置你的Bangumi访问令牌")
            return
            
        if bangumi_input_csv == '请输入你的Bangumi导入文件名.csv':
            logging.error("请在config.ini的[BangumiMigrate]部分设置你的Bangumi导入文件名")
            return
            
        # 构建CSV文件路径（当前目录下）
        csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), bangumi_input_csv)
        
        if not os.path.exists(csv_path):
            logging.error(f"CSV文件不存在: {csv_path}")
            return
            
        # 读取CSV文件
        logging.info(f"开始读取CSV文件: {csv_path}")
        df = pd.read_csv(csv_path)
        logging.info(f"成功读取CSV文件，共{len(df)}条记录")
        
        # 检查必要的列是否存在
        required_columns = ['ID', '状态']
        for col in required_columns:
            if col not in df.columns:
                logging.error(f"CSV文件缺少必要的列: {col}")
                return
                
        # 记录进度配置
        if auto_complete:
            logging.info("已启用自动标满进度功能，所有'看过'状态的条目将被标记为看完")
        else:
            logging.info("未启用自动标满进度功能，将根据'看到'列的值更新进度")
                
        # 使用线程池进行并发处理
        with ThreadPoolExecutor() as executor:
            futures = []

            # 提交每一行数据的处理任务到线程池
            for row in df.itertuples(index=False):
                future = executor.submit(process_row, row, API_URL, wait_time, bangumi_access_token, auto_complete)
                futures.append(future)

            # 等待所有任务完成
            wait(futures)
            
        logging.info("所有数据处理完成")
            
    except Exception as e:
        logging.error(f"程序执行错误: {e}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error(f"程序执行过程中发生未捕获的异常: {e}")
    finally:
        # 添加这行代码使窗口不会在程序执行完毕后立即关闭
        input("\n程序执行完成，按回车键退出...")