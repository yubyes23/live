import os
import re
import requests
import concurrent.futures
import random

# ===============================
# 配置区 (核心修改：目标切换为私库映射目录)
# ===============================
M3U_DIR = os.path.join("repo_live", "zubo") # 💡 锁定私库的 zubo 文件夹
SAMPLE_COUNT = 3
CHECK_TIMEOUT = 10
SKIP_FILE = "zuboall.m3u"  # 汇合大文件不参与清理探测

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def check_link(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=CHECK_TIMEOUT, stream=True)
        if response.status_code == 200:
            return True
        return False
    except:
        return False

def is_m3u_alive(file_path):
    try:
        with open(file_path, "r", encoding="utf-8", errors='ignore') as f:
            content = f.read()
        
        if not content.strip() or "#EXTM3U" not in content:
            return False
        
        links = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', content)
        if not links:
            return False
        
        random.shuffle(links)
        test_links = links[:SAMPLE_COUNT]
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=SAMPLE_COUNT) as executor:
            results = list(executor.map(check_link, test_links))
        
        return any(results)
    except:
        return False

def merge_all_m3u(zubo_dir, output_name):
    """
    就地将私库 zubo 目录下所有清洗存活的单文件，合并为 zuboall.m3u
    """
    output_path = os.path.join(zubo_dir, output_name)
    print(f"\n🔄 开始将存活源合并构建至私库大表: {output_name} ...")
    
    # 动态获取当前清理后剩余的文件
    active_files = [f for f in os.listdir(zubo_dir) if f.lower().endswith(".m3u") and f != output_name]
    active_files.sort()
    
    merged_channels = []
    for filename in active_files:
        file_path = os.path.join(zubo_dir, filename)
        category = os.path.splitext(filename)[0]
        
        try:
            with open(file_path, "r", encoding="utf-8", errors='ignore') as f:
                lines = f.readlines()
                
            current_info = ""
            for line in lines:
                line_str = line.strip()
                if not line_str or line_str.startswith("#EXTM3U"):
                    continue
                
                if line_str.startswith("#EXTINF"):
                    current_info = line_str
                    if "group-title=" not in current_info:
                        current_info = current_info.replace("#EXTINF:-1,", f'#EXTINF:-1 group-title="{category}",')
                elif line_str.startswith("http"):
                    if current_info:
                        merged_channels.append(f"{current_info}\n{line_str}")
                        current_info = ""
                    else:
                        merged_channels.append(f"#EXTINF:-1 group-title=\"{category}\",未知频道\n{line_str}")
        except Exception as e:
            print(f"⚠️ 读取汇总 {filename} 失败: {e}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write("\n".join(merged_channels))
    print(f"✨ 汇合成功！已重新打包 {len(merged_channels)} 个存活组播频道。")

def main():
    if not os.path.exists(M3U_DIR):
        print(f"❌ 目录 {M3U_DIR} 不存在，请确保私库克隆成功且包含 zubo 文件夹。")
        return
    
    print(f"🔍 开始对私库映射目录 [{M3U_DIR}] 进行失效清理...")
    
    files = [f for f in os.listdir(M3U_DIR) if f.lower().endswith(".m3u") and f != SKIP_FILE]
    
    removed_count = 0
    kept_count = 0
    
    for filename in files:
        file_path = os.path.join(M3U_DIR, filename)
        print(f"📄 正在检测: {filename} ... ", end="", flush=True)
        
        if is_m3u_alive(file_path):
            print("✅ [存活] 保留")
            kept_count += 1
        else:
            print("❌ [失效] 从工作区移除")
            os.remove(file_path)
            removed_count += 1
    
    print(f"\n✨ 清理统计: 本次保留 {kept_count} 个文件，移除了 {removed_count} 个失效文件。")
    
    # 💡 自动对清理完剩下的文件进行全新合并汇总
    merge_all_m3u(M3U_DIR, SKIP_FILE)

if __name__ == "__main__":
    main()
