import os
import shutil
import re

# ================= 配置区 (核心修改：锁定私库目录) =================
# 💡 指向私库下的 hotel_output.txt
HOTEL_OUTPUT = os.path.join("repo_live", "hotel_output.txt")
# 💡 重新洗版生成的 M3U 目录存放在私库根目录下的 hotels 文件夹中
REBORN_DIR = os.path.join("repo_live", "hotels")
LOGO_BASE_URL = "https://tb.yubo.qzz.io/logo/"
# ==================================================================

def clean_channel_name(name):
    name = re.sub(r'(高清|标清|普清|超清|超高清|H\.265|4K|HD|SD|hd|sd)', '', name, flags=re.I)
    name = re.sub(r'[\(\)\[\]\-\s]+', '', name)
    return name.strip()

def rebuild():
    if not os.path.exists(HOTEL_OUTPUT): 
        print(f"❌ 错误: 在私库空间中找不到大表源文件 [{HOTEL_OUTPUT}]")
        return
        
    # 🚨 安全修正：为了防止私库中存在的其他定制文件、历史文件被误删，
    # 我们取消了 shutil.rmtree(REBORN_DIR)，直接在此目录下进行增量写入与覆盖
    os.makedirs(REBORN_DIR, exist_ok=True)

    with open(HOTEL_OUTPUT, "r", encoding="utf-8") as f:
        content = f.read().strip().split("\n\n")

    all_m3u = ["#EXTM3U"]
    for section in content:
        lines = section.strip().split("\n")
        if not lines or not lines[0]: continue
        host = lines[0].split(",")[0]
        safe_host = host.replace('.', '_').replace(':', '_')
        
        single_m3u = ["#EXTM3U"]
        for cl in lines[1:]:
            if "," in cl:
                name, url = cl.split(",", 1)
                clean_n = clean_channel_name(name)
                header = f'#EXTINF:-1 tvg-name="{clean_n}" tvg-logo="{LOGO_BASE_URL}{clean_n}.png" group-title="Hotel_{host}",{clean_n}'
                single_m3u.extend([header, url])
                all_m3u.extend([header, url])
        
        # 写入单个节点的 M3U 文件
        with open(os.path.join(REBORN_DIR, f"REBORN_{safe_host}.m3u"), "w", encoding="utf-8") as f_out:
            f_out.write("\n".join(single_m3u))

    # 写入聚合总表
    with open(os.path.join(REBORN_DIR, "ALL.m3u"), "w", encoding="utf-8") as f_all:
        f_all.write("\n".join(all_m3u))
        
    print(f"🌟 增量洗版及多 M3U 打包完成！输出至私库 [{REBORN_DIR}]")

if __name__ == "__main__":
    rebuild()
