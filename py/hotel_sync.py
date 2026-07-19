import os
import re
import requests
import time
from urllib.parse import urlparse

# ================= 配置区 =================
SOURCE_URLS = [
    "https://boyu.ccwu.cc/sub1",
    "https://theresa23-docker.hf.space/sub?K6oomsxl=txt",
    "https://iptv-spider-production-86ca.up.railway.app/sub?VwbZmAYm=txt"
    
]
# 直接定向到本地克隆好的私库对应的 hotel 目录
OUTPUT_DIR = os.path.join("repo_live", "hotel")
IP_API = "http://ip-api.com/json/{}?fields=status,regionName,city&lang=zh-CN"
# ==========================================

def get_ip_location(ip):
    try:
        time.sleep(1) # 频率限制保护
        r = requests.get(IP_API.format(ip), timeout=5)
        data = r.json()
        if data.get('status') == 'success':
            reg = data.get('regionName', '').replace('省', '').replace('市', '')
            cit = data.get('city', '').replace('省', '').replace('市', '')
            return reg if reg == cit else f"{reg}{cit}"
    except: 
        pass
    return "未知属地"

def run():
    print("📥 正在运行 Hotel 同步...")
    
    # 确保工作流已经正确创建了私库映射根目录
    if not os.path.exists(os.path.dirname(OUTPUT_DIR)):
        print("❌ 未检测到私库工作目录 repo_live，请检查工作流配置！")
        return

    # 🚨 安全修正：同样删掉这里的 shutil.rmtree(OUTPUT_DIR)
    # 拒绝清空目录，新旧文件和平共处
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    ip_groups = {}
    total_lines_parsed = 0
    
    for url in SOURCE_URLS:
        print(f"📥 正在获取源数据: {url}")
        try:
            res = requests.get(url, timeout=15)
            res.encoding = 'utf-8' 
            lines = res.text.split('\n')
            print(f"   成功下载，共获取到 {len(lines)} 行原始数据。")
        except Exception as e:
            print(f"❌ 获取源失败 ({url}): {e}")
            continue 

        for line in lines:
            line = line.strip()
            if not line or "," not in line or "#genre#" in line: 
                continue
                
            try:
                name, stream_url = line.split(',', 1)
                name = name.strip()
                stream_url = stream_url.strip()
                
                if not stream_url.startswith("http"): continue
                host = urlparse(stream_url).netloc
                if not host: continue
                
                if re.search(r'(CCTV)(\d+)', name, re.IGNORECASE):
                    name = re.sub(r'(CCTV)(\d+)', r'\1-\2', name, flags=re.IGNORECASE)
                
                if host not in ip_groups:
                    if ':' in host:
                        ip, port = host.split(':', 1)
                    else:
                        ip, port = host, "80"
                    
                    print(f"🔍 发现新 IP 节点: {ip} ... ", end="", flush=True)
                    loc = get_ip_location(ip)
                    print(f"结果: {loc}")
                    
                    ip_groups[host] = {
                        "filename": f"{loc}_{ip.replace('.', '_')}_{port}.m3u", 
                        "channels": [],
                        "seen_sign": set()
                    }
                
                sign = f"{name}_{stream_url}"
                if sign not in ip_groups[host]["seen_sign"]:
                    ip_groups[host]["channels"].append({"name": name, "url": stream_url})
                    ip_groups[host]["seen_sign"].add(sign)
                    total_lines_parsed += 1
                    
            except Exception as line_err:
                continue

    print(f"\n📊 解析阶段结束。共清洗出 {total_lines_parsed} 个有效频道。")
    if not ip_groups:
        print("⚠️ 本次未解析到任何有效的酒店源数据。")
        return

    print(f"🚀 开始本地写入 {len(ip_groups)} 个酒店源文件到私库工作区...")
    for host, data in ip_groups.items():
        filename = data["filename"]
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        # 增量模式：直接写入（重名覆盖，不重名新增）
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for ch in data["channels"]:
                f.write(f'#EXTINF:-1 group-title="Hotel_{host}",{ch["name"]}\n{ch["url"]}\n')
        
    print("\n✨ Hotel 酒店源私库增量更新完毕！")

if __name__ == "__main__":
    run()
