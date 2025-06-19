# -*- coding: utf-8 -*-
import csv
import os
import shlex
import logging
import shutil
import re
import difflib
from datetime import date, datetime

# 日志配置
title = 'dedup.log'
logging.basicConfig(
    filename=title,
    filemode='a',
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.INFO
)
logging.info('脚本启动')

# 可选依赖：用于更智能的编码检测
try:
    import chardet
    logging.info('检测到 chardet，可进行高级编码检测')
except ImportError:
    chardet = None
    logging.info('未安装 chardet，仅使用 BOM 检测')


def detect_encoding(path, sample_size=8192):
    logging.info(f'开始检测编码: {path}')
    try:
        with open(path, 'rb') as f:
            raw = f.read(sample_size)
    except Exception as e:
        logging.error(f'读取文件二进制失败: {path}, 错误: {e}')
        return 'utf-8'
    # BOM 检测
    boms = [
        (b"\xff\xfe\x00\x00", 'utf-32'),
        (b"\x00\x00\xfe\xff", 'utf-32-be'),
        (b"\xff\xfe", 'utf-16'),
        (b"\xfe\xff", 'utf-16-be'),
        (b"\xef\xbb\xbf", 'utf-8-sig'),
    ]
    for bom, enc in boms:
        if raw.startswith(bom):
            logging.info(f'检测到 BOM 编码: {enc} ({path})')
            return enc
    if chardet:
        result = chardet.detect(raw)
        enc = result.get('encoding')
        logging.info(f'chardet 检测结果: {enc}, 置信度: {result.get("confidence")}')
        if enc and enc.lower() != 'ascii':
            return enc
    return 'utf-8'


# 新增：获取新旧文件共同且非忽略的列名
def get_common_cols(headers):
    """
    输入多个header（如[新, 旧1, 旧2]），返回它们共同拥有且不在ignore_cols的列名（顺序按新文件header顺序）。
    """
    sets = [set(h) for h in headers]
    common = set.intersection(*sets)
    #这里可以自定义需要忽略的值，内容以逗号隔开，例如"watched_at"（imdb文件观看时间值） "看到"（Bangumi进度值） ,"","" 
    ignore_cols = {"中文","日文","放送","排名","评分","话数","标签","我的评价","我的简评","私密","更新时间","watched_at"}
    common = [col for col in headers[0] if col in common and col not in ignore_cols]
    return common

# 修改：deduplicate 支持指定用哪些列去比对
def deduplicate(old_paths, encoding, use_cols):
    keys = set()
    for p in old_paths:
        logging.info(f'读取旧文件: {p}')
        with open(p, newline='', encoding=encoding) as f:
            reader = csv.reader(f)
            header = next(reader)
            # 找出当前旧文件header中共同需要对比的列索引
            col_indices = [i for i, col in enumerate(header) if col in use_cols]
            for row in reader:
                keys.add(tuple(row[i] for i in col_indices))
        logging.info(f'累计键数: {len(keys)}')
    return keys

# 修改：filter_new_lines 也只比对用共同列
def filter_new_lines(new_path, keys, encoding, use_cols):
    logging.info(f'过滤新文件: {new_path}')
    with open(new_path, 'r', encoding=encoding, newline='') as f:
        lines = f.readlines()
    reader = csv.reader(lines)
    header = next(reader)
    raw_header = ''.join(lines[:reader.line_num]).lstrip('\ufeff')
    col_indices = [i for i, col in enumerate(header) if col in use_cols]

    kept = []
    prev = reader.line_num
    for row in reader:
        curr = reader.line_num
        record = ''.join(lines[prev:curr])
        prev = curr
        key = tuple(row[i] for i in col_indices)
        if key not in keys:
            kept.append(record)
    logging.info(f'保留行数: {len(kept)}')
    return raw_header, kept

# 修改：主流程中自动获得共同列并传递
def process_batch_auto(old_paths, new_path):
    logging.info('模式1: 自动模式开始处理')
    enc_new = detect_encoding(new_path)
    enc_old = detect_encoding(old_paths[0])
    # 1. 先读取新旧文件header
    with open(new_path, encoding=enc_new) as f:
        header_new = next(csv.reader(f))
    headers_old = []
    for op in old_paths:
        with open(op, encoding=enc_old) as f:
            headers_old.append(next(csv.reader(f)))
    # 2. 求新旧文件共同列
    use_cols = get_common_cols([header_new] + headers_old)
    # 3. 按共同列做去重
    keys = deduplicate(old_paths, enc_old, use_cols)
    header, kept = filter_new_lines(new_path, keys, enc_new, use_cols)

    # 输出结果文件
    ds = f"{date.today().month:02d}.{date.today().day:02d}"
    base = os.path.splitext(os.path.basename(new_path))[0]
    out_name = f"{base}_New_{ds}.csv"
    out_path = os.path.join(os.path.dirname(new_path), out_name)
    with open(out_path, 'w', encoding=enc_new, newline='') as f:
        f.write(header)
        f.writelines(kept)
    print(f"去重完成: {out_path}")
    logging.info(f'生成去重文件: {out_path} (编码:{enc_new})')

    # 移动或重命名原文件到 dedup 目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    de_dup_dir = os.path.join(script_dir, "dedup")
    os.makedirs(de_dup_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(new_path))[0]
    if re.search(r"(?:_\d{2}\.\d{2})$|(?:_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})$", stem):
        dest_name = os.path.basename(new_path)
    else:
        ctime = os.path.getctime(new_path)
        dt = datetime.fromtimestamp(ctime)
        ct_suffix = f"{dt.month:02d}.{dt.day:02d}"
        ext = os.path.splitext(new_path)[1]
        dest_name = f"{stem}_{ct_suffix}{ext}"
    dest = os.path.join(de_dup_dir, dest_name)
    shutil.move(new_path, dest)
    os.utime(dest, None)
    print(f"已移动原文件到: {dest}")
    logging.info(f'原文件移动/重命名: {dest_name}')

def process_batch_manual(old_paths, new_path):
    logging.info('模式2: 手动模式开始处理')
    enc_new = detect_encoding(new_path)
    enc_old = detect_encoding(old_paths[0])
    # 1. 先读取新旧文件header
    with open(new_path, encoding=enc_new) as f:
        header_new = next(csv.reader(f))
    headers_old = []
    for op in old_paths:
        with open(op, encoding=enc_old) as f:
            headers_old.append(next(csv.reader(f)))
    # 2. 求新旧文件共同列
    use_cols = get_common_cols([header_new] + headers_old)
    # 3. 按共同列做去重
    keys = deduplicate(old_paths, enc_old, use_cols)
    header, kept = filter_new_lines(new_path, keys, enc_new, use_cols)

    # 输出结果文件
    ds = f"{date.today().month:02d}.{date.today().day:02d}"
    base = os.path.splitext(os.path.basename(new_path))[0]
    out_name = f"{base}_New_{ds}.csv"
    out_path = os.path.join(os.path.dirname(new_path), out_name)
    with open(out_path, 'w', encoding=enc_new, newline='') as f:
        f.write(header)
        f.writelines(kept)
    print(f"去重完成: {out_path}")
    logging.info(f'手动模式生成去重文件: {out_path}')

def auto_select_files():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    logging.info(f'模式1日志调试: dedup 目录自动选择，脚本目录={script_dir}')
    de_dup_dir = os.path.join(script_dir, "dedup")
    if not os.path.isdir(de_dup_dir):
        os.makedirs(de_dup_dir, exist_ok=True)
        print(f"未找到目录: {de_dup_dir}，已自动创建。请将旧文件放入后重试。")
        logging.info(f'已创建缺失目录: {de_dup_dir}')
        return []

    old_files = [os.path.join(de_dup_dir, f) for f in os.listdir(de_dup_dir) if f.lower().endswith('.csv')]
    new_files = [os.path.join(script_dir, f) for f in os.listdir(script_dir)
                 if f.lower().endswith('.csv') and "_New_" not in f]

    if not old_files:
        print(f"在目录 {de_dup_dir} 中未找到任何 CSV 文件，请先放入旧文件。")
        return []
    if not new_files:
        print(f"在脚本目录未找到任何新 CSV 文件。")
        return []

    # 基于相似度匹配新旧文件
    def clean(name):
        s = name
        # 去除 MM.DD 日期后缀
        s = re.sub(r'_(\d{2}\.\d{2})$', '', s)
        # 去除完整时间戳后缀 YYYY-MM-DD_HH-MM-SS
        s = re.sub(r'_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$', '', s)
        # 去除带点的数字序号后缀，如 _9 或 _2 或 _09.04
        s = re.sub(r'_[0-9]+(?:\.[0-9]+)*$', '', s)
        # 去除纯数字点数字后缀，如 1.12 或 2.3.4
        s = re.sub(r'[0-9]+(?:\.[0-9]+)+$', '', s)
        return s

    mapping = {}
    threshold = 0.85
    for old in old_files:
        key = clean(os.path.splitext(os.path.basename(old))[0])
        best_ratio, best_new = 0, None
        for new in new_files:
            new_key = clean(os.path.splitext(os.path.basename(new))[0])
            ratio = difflib.SequenceMatcher(None, key, new_key).ratio()
            if ratio > best_ratio or (
               ratio == best_ratio and os.path.getmtime(new) > os.path.getmtime(best_new or new)
            ):
                best_ratio, best_new = ratio, new
        if best_ratio >= threshold:
            mapping.setdefault(best_new, []).append(old)
            logging.info(f'匹配成功: {old} -> {best_new}, 相似度 {best_ratio:.2f}')
        else:
            logging.info(f'旧文件 {old} 无匹配的新文件 (最高相似度 {best_ratio:.2f})')
    return [(olds, new) for new, olds in mapping.items()]

def auto_select_special():
    """特殊模式：扫描脚本所在目录的特定新文件，并在兄弟文件夹根目录中扫描特定旧文件"""
    logging.info('模式3: 进入特殊模式 auto_select_special')
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(script_dir)
    folder = os.path.basename(script_dir)
    # 根据脚本目录选择不同的新文件模式
    if folder == "Bangumi to Trakt":
        sibling = "Trakt To Bangumi"
        # 仅匹配 Bangumi 相关文件
        new_patterns = [
            re.compile(r".*Bangumi.*\.csv", re.IGNORECASE)
        ]
    elif folder == "Trakt To Bangumi":
        sibling = "Bangumi to Trakt"
        # 仅匹配 export_*_(history|watchlist).* 文件
        new_patterns = [
            re.compile(r"export_(?:movies|shows|episodes)_(?:history|watchlist).*\.csv", re.IGNORECASE)
        ]
    else:
        logging.error(f'未知脚本目录名称: {folder}')
        print(f"未知脚本目录名称: {folder}")
        return []
    sibling_root = os.path.join(parent_dir, sibling)
    logging.info(f'特殊模式目录信息: script_dir={script_dir}, sibling_root={sibling_root}')
    if not os.path.isdir(sibling_root):
        logging.error(f'未找到目录: {sibling_root}')
        print(f"未找到目录: {sibling_root}")
        return []

    # 匹配新文件
    logging.info(f'使用的新文件匹配正则: {[p.pattern for p in new_patterns]}')
    new_files = [os.path.join(script_dir, f) for f in os.listdir(script_dir)
                 if any(pat.match(f) for pat in new_patterns) and "_New_" not in f]
    logging.info(f'匹配到的新文件: {new_files}')
    if not new_files:
        logging.warning('未找到符合条件的新文件。')
        print("未找到符合条件的新文件。")
        return []

    # 匹配旧文件：根据当前目录选择不同的旧文件
    old_files = []
    if folder == "Bangumi to Trakt":
        # 在 sibling_root 中匹配 bangumi_export.csv
        logging.info('特殊模式: 匹配旧文件 bangumi_export.csv')
        for f in os.listdir(sibling_root):
            if re.match(r"bangumi_export\.csv$", f, re.IGNORECASE):
                old_files.append(os.path.join(sibling_root, f))
    else:  # Trakt To Bangumi
        logging.info('特殊模式: 匹配旧文件 trakt_formatted.csv 和 temp_trakt_formatted.csv')
        for fname in ["trakt_formatted.csv", "temp_trakt_formatted.csv"]:
            path = os.path.join(sibling_root, fname)
            if os.path.isfile(path):
                old_files.append(path)
    logging.info(f'匹配到的旧文件: {old_files}')
    if not old_files:
        logging.warning('未找到符合条件的旧文件。')
        print("未找到符合条件的旧文件。")
        return []

    # 多对一：所有新文件共用同一组旧文件
    pairs = [(old_files, new) for new in new_files]
    logging.info(f'特殊模式匹配完成: {pairs}')
    return pairs


def main():
    print("欢迎使用 Bangumi-to-Trakt 、 Trakt-to-Bangumi 项目专用去重脚本 v8.9")
    print("https://github.com/wan0ge/Bangumi-to-Trakt")
    print("https://github.com/wan0ge/Trakt-to-Bangumi")
    print("-" * 60)
    print("请选择模式")
    print("模式1: 自动选择文件：根据dedup文件夹内的旧文件自动选择脚本目录的新文件 去重后自动移动原至dedup")
    print("模式2: 手动选择文件：手动输入新旧文件路径，支持拖拽，多个旧文件用空格或逗号分隔，不移动原文件")
    print("模式3: 特殊选择模式：自动选择脚本目录特定新文件，并在兄弟文件夹匹配特定旧文件（使用反向项目对面平台转换后的文件作为旧文件去重）")
    print("-" * 60)

    while True:
        mode = input("选择模式 (1=自动, 2=手动, 3=特殊, 其他退出): ").strip()
        if mode == '1':
            logging.info('用户选择模式1')
            pairs = auto_select_files()
            if not pairs:
                print("文件选择失败，返回模式选择。")
                continue
            print("检测到以下待处理文件对：")
            for i, (olds, new) in enumerate(pairs, 1):
                print(f"  {i}. 旧文件:")
                for old in olds:
                    print(f"    {old}")
                print(f"    新文件: {new}")
            if input("全部确认并去重? (y/n): ").strip().lower() == 'y':
                for olds, new in pairs:
                    try:
                        process_batch_auto(olds, new)
                    except Exception as e:
                        print(f"{olds} -> {new} 处理失败: {e}")

        elif mode == '2':
            logging.info('用户选择模式2')
            inp = input("输入旧文件列表 (空格或逗号分隔): ").strip()
            if not inp:
                break
            old_paths = shlex.split(inp.replace(',', ' '))
            new_path = input("输入新文件路径: ").strip().strip("'\"")
            if not new_path:
                break
            print(f"准备去重:\n  旧文件: {old_paths}\n  新文件: {new_path}")
            if input("确认? (y/n): ").strip().lower() == 'y':
                try:
                    process_batch_manual(old_paths, new_path)
                except Exception as e:
                    print(f"失败: {e}")

        elif mode == '3':
            logging.info('用户选择模式3')
            pairs = auto_select_special()
            if not pairs:
                print("文件选择失败，返回模式选择。")
                continue
            print("检测到以下待处理文件对：")
            for i, (olds, new) in enumerate(pairs, 1):
                print(f"  {i}. 旧文件:")
                for old in olds:
                    print(f"    {old}")
                print(f"    新文件: {new}")
            if input("全部确认并去重? (y/n): ").strip().lower() == 'y':
                for olds, new in pairs:
                    try:
                        process_batch_manual(olds, new)
                    except Exception as e:
                        print(f"{olds} -> {new} 处理失败: {e}")
        else:
            break

        if input("继续下一批? (y/n): ").strip().lower() != 'y':
            break

    print("结束")
    logging.info('脚本结束')


if __name__ == '__main__':
    main()
