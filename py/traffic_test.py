import requests
import time
import random
import re
import os
import json
import urllib3
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

# 1. 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ================= 配置区 (核心修改：锁定私库目录) =================
# 💡 精准重映射：从私库目录中读取前面由洗版脚本生成的 ALL.m3u 总表
SOURCE_M3U = os.path.join("repo_live", "hotels", "ALL.m3u")
# 💡 精准重映射：生成的测速报告直接放在私库根目录里
OUTPUT_TXT = os.path.join("repo_live", "traffic_report.txt")
OUTPUT_JSON = os.path.join("repo_live", "traffic_summary.json")

TEST_DURATION = 10  # 每个 ID 测试 10 秒
SAMPLES_PER_IP = 2  # 每个 IP 随机抽 2 个 ID 压测
MAX_WORKERS = 5     # 并行线程数
# ==================================================================

def test_stream_traffic(name, url):
    """模拟播放并统计流量，计算 Mbps"""
    ip_port = urlparse(url).netloc
    start_time = time.time()
    total_bytes = 0
    speeds_mbps = []
    
    headers = {'User-Agent': 'Mozilla/5.0 (Viera; rv:34.0) Gecko/20100101 Firefox/34.0'}
    
    try:
        # 获取 m3u8 索引
        r = requests.get(url, timeout=5, headers=headers, verify=False)
        if r.status_code != 200: return None
        
        # 提取 .ts 切片
        lines = r.text.split('\n')
        base_dir = url.rsplit('/', 1)[0]
        ts_lines = [l.strip() for l in lines if l.strip() and not l.startswith('#')]
        if not ts_lines: return None

        # 循环下载切片
        while time.time() - start_time < TEST_DURATION:
            target_ts = ts_lines[-2:] if len(ts_lines) > 2 else ts_lines
            for ts_path in target_ts:
                if time.time() - start_time > TEST_DURATION: break
                ts_url = ts_path if ts_path.startswith('http') else f"{base_dir}/{ts_path}"
                
                ts_start = time.time()
                try:
                    ts_r = requests.get(ts_url, timeout=5, headers=headers, stream=True, verify=False)
                    chunk_bytes = 0
                    for chunk in ts_r.iter_content(chunk_size=128*1024):
                        if chunk:
                            chunk_bytes += len(chunk)
                            total_bytes += len(chunk)
                            if time.time() - start_time > TEST_DURATION: break
                    
                    ts_duration = time.time() - ts_start
                    if ts_duration > 0 and chunk_bytes > 5120:
                        mbps = (chunk_bytes * 8) / (ts_duration * 1024 * 1024)
                        speeds_mbps.append(mbps)
                except: continue
            time.sleep(0.5) 

    except:
        return None

    test_time = time.time() - start_time
    if test_time > 0 and speeds_mbps:
        avg_speed = (total_bytes * 8) / (test_time * 1024 * 1024)
        max_speed = max(speeds_mbps)
        min_speed = min(speeds_mbps)
        stability = 1 - ((max_speed - min_speed) / avg_speed) if avg_speed > 0 else 0
        stability = max(0, min(1, stability))
        
        return {
            "name": name, "ip_port": ip_port,
            "avg_mbps": round(avg_speed, 2), "max_mbps": round(max_speed, 2),
            "stability": round(stability, 2)
        }
    return None

def save_reports(results, group_summary):
    """保存结果"""
    with open(OUTPUT_TXT, 'w', encoding='utf-8') as f:
        f.write("="*75 + "\n")
        f.write(f"📡 IPTV 酒店源流量测速报告 | 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*75 + "\n")
        f.write(f"{'服务器 (IP:Port)':<25} | {'频道':<15} | {'速度':<12} | {'稳定性'}\n")
        f.write("-" * 75 + "\n")
        for res in results:
            f.write(f"{res['ip_port']:<25} | {res['name'][:12]:<15} | {res['avg_mbps']:>6} Mbps | {res['stability']*100:>3.0f}%\n")
        
        f.write("\n📊 综合汇总 (Summary):\n")
        for ip, summ in group_summary.items():
            f.write(f"{ip:<25} | 有效频道:{summ['alive_count']} | 平均:{summ['avg_mbps']:>5} Mbps\n")

    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump({"summary": group_summary, "details": results}, f, ensure_ascii=False, indent=2)

def main():
    print(f"🚀 开始进行私库内 IPTV 多源实际网络吞吐测速...")
    print(f"📂 目标扫描总表: {os.path.abspath(SOURCE_M3U)}")
    
    if not os.path.exists(SOURCE_M3U):
        print(f"❌ 错误: 找不到源文件 {SOURCE_M3U}，请确保前面运行了洗版重建脚本。")
        return

    with open(SOURCE_M3U, 'r', encoding='utf-8') as f:
        content = f.read()

    groups = {}
    lines = content.split('\n')
    for i in range(len(lines)):
        current_line = lines[i].strip()
        if current_line.startswith('#EXTINF') and i+1 < len(lines):
            url = lines[i+1].strip()
            if url.startswith('http'):
                try:
                    ip_port = urlparse(url).netloc
                    if not ip_port: continue
                    if ip_port not in groups: groups[ip_port] = []
                    
                    name = "Unknown"
                    if ',' in current_line:
                        parts = current_line.split(',', 1)
                        if len(parts) > 1 and parts[1].strip():
                            name = parts[1].strip()
                        else:
                            tvg_match = re.search(r'tvg-name="([^"]+)"', current_line)
                            if tvg_match:
                                name = tvg_match.group(1).strip()
                    
                    groups[ip_port].append((name, url))
                except Exception as parse_err:
                    continue

    groups = {k: v for k, v in groups.items() if v}
    if not groups:
        print("⚠️ 总表 M3U 中未能成功读取到任何有效切片播放地址。")
        return

    tasks = []
    for ip_port, urls in groups.items():
        if not urls: continue
        samples = random.sample(urls, min(len(urls), SAMPLES_PER_IP))
        tasks.extend(samples)

    print(f"📡 识别到 {len(groups)} 个 IP 源，准备测试 {len(tasks)} 个样本...")

    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(test_stream_traffic, n, u) for n, u in tasks]
        for future in futures:
            try:
                res = future.result()
                if res: results.append(res)
            except Exception as e:
                print(f"⚠️ 线程压测执行异常: {e}")

    group_summary = {}
    for res in results:
        ip = res['ip_port']
        if ip not in group_summary:
            group_summary[ip] = {"alive_count": 0, "speeds": [], "max_mbps": 0}
        s = group_summary[ip]
        s["alive_count"] += 1
        s["speeds"].append(res['avg_mbps'])
        s["max_mbps"] = max(s["max_mbps"], res['max_mbps'])

    for ip, data in group_summary.items():
        if data["speeds"]:
            data["avg_mbps"] = round(sum(data["speeds"]) / len(data["speeds"]), 2)
        else:
            data["avg_mbps"] = 0.0
        del data["speeds"]

    save_reports(results, group_summary)
    print(f"✅ 测速及吞吐评估完成！报告已安全写入私库空间。")

if __name__ == "__main__":
    main()
