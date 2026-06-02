# 遠端 AIBox 診斷指令

複製下面這整段，貼到 Cursor Terminal 執行：

```bash
echo "=== 1. .env syntax check ===" && bash -c 'source /Users/daniel/GitHub/AIBox/api/.env' 2>&1; echo "exit: $?" && echo "" && echo "=== 2. debug trace ===" && bash -x /Users/daniel/GitHub/AIBox/start.sh status 2>&1 | head -20 && echo "" && echo "=== 3. tools ===" && which curl lsof python3 2>&1
```

執行後把輸出貼回來給我。
