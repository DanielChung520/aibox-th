SYSTEM_PROMPT = """你是報表生成專家，專精於將 JSON 資料轉換為視覺化 HTML 報表。

核心原則：
1. 資料隔離 - 永遠不輸出原始資料，只輸出圖表代碼
2. 本地處理 - 所有分析在本地完成，不呼叫外部 API
3. 標準化輸出 - 輸出統一格式的 HTML 報告

圖表選擇指南：
- 餅圖（PieChart）：展示各類別佔比/組成
- 線圖（LineChart）：展示時間趨勢/變化
- 柱狀圖（BarChart）：展示分類比較/排名
- 散點圖（ScatterChart）：展示相關性/分布
- 雷達圖（RadarChart）：展示多維度比較

HTML 報告格式要求：
1. 使用 Recharts CDN（可離線使用）
2. 響應式設計（支援不同螢幕尺寸）
3. 統一的 Header（標題、製作日期、作者）
4. 圖表之後要有分析文字

分析文字要求：
- 識別關鍵趨勢
- 標註異常值或特別發現
- 提供具體的業務解讀
- 用繁體中文回覆

輸出嚴格禁止：
- 不要輸出任何原始資料內容
- 不要輸出可以逆向取得資料的內容
- 只輸出 HTML 與分析文字"""

CHART_TEMPLATES = {
    "pie": '''
    <PieChart width={800} height={400}>
      <Pie
        data={data}
        cx="50%"
        cy="50%"
        labelLine={false}
        label={({name, percent}) => `${name}: ${(percent * 100).toFixed(0)}%`}
        outerRadius={150}
        fill="#8884d8"
        dataKey="value"
      >
        {data.map((entry, index) => (
          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
        ))}
      </Pie>
      <Tooltip />
      <Legend />
    </PieChart>''',
    "line": '''
    <LineChart width={800} height={400} data={data}>
      <XAxis dataKey="name" />
      <YAxis />
      <Tooltip />
      <Legend />
      <Line type="monotone" dataKey="value" stroke="#8884d8" strokeWidth={2} />
    </LineChart>''',
    "bar": '''
    <BarChart width={800} height={400} data={data}>
      <XAxis dataKey="name" />
      <YAxis />
      <Tooltip />
      <Legend />
      <Bar dataKey="value" fill="#8884d8" />
    </BarChart>''',
    "scatter": '''
    <ScatterChart width={800} height={400}>
      <XAxis dataKey="x" name={xKey} />
      <YAxis dataKey="y" name={yKey} />
      <Tooltip cursor={{ strokeDasharray: '3 3' }} />
      <Scatter data={data} fill="#8884d8" />
    </ScatterChart>''',
    "area": '''
    <AreaChart width={800} height={400} data={data}>
      <XAxis dataKey="name" />
      <YAxis />
      <Tooltip />
      <Legend />
      <Area type="monotone" dataKey="value" stroke="#8884d8" fill="#8884d8" fillOpacity={0.3} />
    </AreaChart>''',
}

RECHART_CDN = """<script src="https://unpkg.com/recharts@2.15.0/umd/Recharts.js"></script>"""
