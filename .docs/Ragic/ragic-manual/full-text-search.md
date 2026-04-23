---
title: 全文檢索
url: https://www.ragic.com/intl/zh-TW/doc-user/17/full-text-search
category: Chapter 17
tags: [full-text-search]
---

# 全文檢索


## IMPORTANT CONCEPTS


## RESOURCES


## PERSONAL


## 群組


## 提高字詞搜尋相關度


## 範圍搜尋


## 鄰近搜尋


## 模糊搜尋


## 萬用字元搜尋(目前僅支援英數字)


## -


## NOT


## +


## AND


## OR


## 布林運算子


## 欄位搜尋


## 截圖能夠讓我們更清楚了解您的建議：


## 請針對上方勾選項目提供詳細說明：


## 搜尋列的語法


## 全文檢索

你可以透過上方的搜尋列來做全文檢索，除了利用滑鼠點擊搜尋列，也可以用快捷鍵 fn+F3 來使用此功能。如果你是在首頁做全文檢索的話，會針對所有表單的資料做搜尋(你有權限看到的表單資料），如果你是在某一張表單內做全文檢索的話，就只會針對該張表單顯示搜尋結果。

全文檢索的功能像是搜尋引擎，可以幫助你找到完整資料。當鍵入文字時，也會提供搜尋建議。想要找某一筆特定的資料時，只要知道其中一個資訊就可以透過全文檢索找到，非常方便！

在搜尋後，還可以進一步針對表單的欄位排序。

首頁的全文檢索會列出最近三筆搜尋紀錄。

1. 除非使用正規表示法，全文檢索不能用來搜尋不完全的數據。舉例來說，假設你有一個數值是1234567001，此時就不能直接以最後三位數 「001」 來搜尋。這種情況下，你可以利用左側搜尋列或是列表頁欄位標頭來篩選資料。

2. 目前全文檢索只會搜尋表單頁的內容，因此如果在表單頁將某個欄位設定為隱藏時，即使設定列表頁顯示該欄位，也無法使用全文檢索搜尋該欄位的內容。

在搜尋時，可以寫一些搜尋列的語法來結合不同的字詞，或是使用布林運算子建立較複雜的查詢來找到特定的資料，這與 Google 的語法相似。

也可以修改查詢的字詞來提供更廣泛的搜尋選項。

可以輸入欄位名稱後面加一個「:」再加上你在尋找的字詞，來針對特定欄位搜尋資料。

布林運算子允許字詞藉由邏輯運元結合。 Ragic 支援的布林運算子有：「AND」、「+」、「OR」、「NOT」、「-」。

1. 布林運算子區分大小寫。

2. 使用英文搜尋時，若使用兩個字詞以上做為一個關鍵字使用時，要加上" "，例如想要搜尋的關鍵字是「customer service」，要輸入 "customer service" ，就只會搜尋到同時有 customer service 的資料，如果沒有加上" "，就會也搜尋到只有 customer 或是 service 的資料。使用中文搜尋則不需要加上" "。

OR 運算子是預設的連接運算子，也就是如果沒有加上布林運算子在兩個字詞中間的話，就會預設使用 OR 運算子，可以使用符號||來代替 OR 。

用途：用於擴大搜尋結果範圍。搜尋包含其中任一個關鍵字的資料，而不需要同時包含所有關鍵字。如果在一筆資料裡都沒有找到該字詞，則會找到相符合的資料。

範例：要搜尋文件包含「customer service」或是「customer」。

語法："customer service" customer 或是 "customer service" OR customer

可以使用符號 & 來代替 AND 。

用途：用於縮小搜尋結果範圍。搜尋必須同時包含所有關鍵字的資料，可以讓搜尋結果更加精確。

範例：要搜尋資料包含 「customer service」 和 「Service Issues」。

語法："customer service" AND "Service Issues"

用途：搜尋必須包含特定關鍵字的資料。+ 後面接的第一個字詞代表必須要包含的關鍵字，在第一個字詞後面的字詞則是可能包含的關鍵字。

範例：要搜尋資料包含「customer」，其中可能包含「Service」。

語法：+customer service

可以使用符號 ! 來代替 NOT 。

用途：搜尋排除在 NOT 後面字詞的資料。

範例：要搜尋資料包含「customer service」，但是不包含「Service Issues」。

語法："customer service" NOT "Service Issues"

注意：不能在只有一個字詞時使用，例如：NOT "customer service"。

用途：搜尋排除在 - 後面字詞的資料。

範例：要搜尋資料包含「customer service」，但是不包含「Service Issues」。

---

## 圖片

[圖片1](https://www.ragic.com/sims/file.jsp?a=kb&f=_clipboard1686554732661.png)
[圖片2](https://www.ragic.com/sims/file.jsp?a=kb&f=_clipboard1686555045608.png)
[圖片3](https://www.ragic.com/sims/file.jsp?a=kb&f=_clipboard1697704717061.png)
[圖片4](https://www.ragic.com/sims/file.jsp?a=kb&f=_clipboard1686554785809.png)
