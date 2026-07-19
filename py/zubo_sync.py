import os
import re
import requests
import time

# --- 配置区 ---
SOURCE_URLS = [
    "https://boyu.ccwu.cc/sub2",
    "https://theresa23-docker.hf.space/sub?SbddegLU=txt",
    "https://iptv-spider-production-86ca.up.railway.app/sub?9TyMLVxb=txt"
]
# 直接定向到本地克隆好的私库对应的 zubo 目录
OUTPUT_DIR = os.path.join("repo_live", "zubo")
# --- --- --- ---

def translate_isp(raw_isp):
    if not raw_isp: return "其他"
    isp_str = raw_isp.upper()
    if any(x in isp_str for x in ["CHINANET", "TELECOM", "电信"]): return "电信"
    if any(x in isp_str for x in ["CNC", "UNICOM", "联通"]): return "联通"
    if any(x in isp_str for x in ["MOBILE", "CMI", "铁通", "移动"]): return "移动"
    if any(x in isp_str for x in ["CERNET", "教育网"]): return "教育网"
    if any(x in isp_str for x in ["CRTC", "BROADCAST", "广电"]): return "广电"
    cleaned = re.sub(r'[a-zA-Z\s\.\-_]', '', raw_isp)
    return cleaned if cleaned else "其他"

def get_ip_info(ip):
    try:
        time.sleep(1) # 限制频率，防止被 API 封禁
        response = requests.get(f"http://ip-api.com/json/{ip}?lang=zh-CN", timeout=5)
        data = response.json()
        if data.get('status') == 'success':
            region = data.get('regionName', '').replace("省", "").replace("市", "")
            isp = translate_isp(data.get('isp', ''))
            return f"{region}{isp}"
    except:
        pass
    return "未知"

def main():
    # 确保工作流已经正确创建了私库映射根目录
    if not os.path.exists(os.path.dirname(OUTPUT_DIR)):
        print("❌ 未检测到私库工作目录 repo_live，请检查工作流配置！")
        return
        
    # 🚨 安全修正：不再删除整个文件夹，只确保文件夹存在。
    # 这样旧文件能安全保留，新文件若重名则覆盖，不重名则共存。
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    ip_groups = {}
    
    for source_url in SOURCE_URLS:
        print(f"\n📥 正在获取源数据: {source_url}")
        try:
            r = requests.get(source_url, timeout=15)
            r.encoding = 'utf-8'
            lines = r.text.split('\n')
        except Exception as e:
            print(f"❌ 获取源失败 ({source_url}): {e}")
            continue

        for line in lines:
            line = line.strip()
            if ',' not in line or "#genre#" in line: continue
            parts = line.split(',', 1)
            if len(parts) < 2: continue
            name, url = parts[0].strip(), parts[1].strip()
            
            if re.search(r'(CCTV)(\d+)', name, re.IGNORECASE):
                name = re.sub(r'(CCTV)(\d+)', r'\1-\2', name, flags=re.IGNORECASE)
            
            match = re.search(r'://([\d\.]+):(\d+)', url)
            if match:
                host = match.group(1)
                port = match.group(2)
                key = f"{host}:{port}"
                
                if key not in ip_groups:
                    print(f"🔍 发现新组播 IP 节点: {host} ... ", end="", flush=True)
                    info = get_ip_info(host)
                    print(f"结果: {info}")
                    
                    ip_groups[key] = {
                        "filename": f"{info}_{host.replace('.', '_')}_{port}.m3u",
                        "channels": [],
                        "seen_urls": set()
                    }
                
                if url not in ip_groups[key]["seen_urls"]:
                    ip_groups[key]["channels"].append({"name": name, "url": url})
                    ip_groups[key]["seen_urls"].add(url)

    if not ip_groups:
        print("\n⚠️ 本次未从所有源中解析到任何新的有效数据")
        return

    print(f"\n🚀 开始本地写入 {len(ip_groups)} 个组播 IP 文件到私库工作区...")
    for key, data in ip_groups.items():
        filename = data["filename"]
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        # 增量模式：直接写入（重名覆盖，不重名新增）
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for ch in data["channels"]:
                f.write(f"#EXTINF:-1,{ch['name']}\n{ch['url']}\n")
        print(f"✍️ 已同步生成/覆盖: {filename}")

    print("\n✨ Zubo 私库本地增量更新完毕！")

if __name__ == "__main__":
    main()
