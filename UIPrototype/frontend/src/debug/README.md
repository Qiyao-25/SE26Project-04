# DEBUG ONLY — 定时抓取手动触发 UI
#
# 删除本目录即可去掉前端调试入口，并同步：
# 1. 去掉 SettingsPage 中对 CrawlSchedulerDebugCard 的引用
# 2. 删除后端 app/api/debug_crawl.py 及 main.py 中的注册
# 3. 去掉 PAPERMATE_ENABLE_CRAWL_DEBUG / VITE_ENABLE_CRAWL_DEBUG
