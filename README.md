# tagging-plurk

用 LLM 幫噗浪貼文下標籤。 詳細解說請見：
[LLM API 練習： 台幣三元能做多少事? 幫四千多則噗浪貼文下標籤](https://newtoypia.blogspot.com/2026/08/tagging-plurk.html)

## 1. 建立資料庫

(只做一次) 用 sqlite3 (或 litecli) 建立噗文與標籤資料庫 plurk_tags.db：

```
CREATE TABLE "plurk" (
    id TEXT PRIMARY KEY,    -- 噗浪官方 ID ( e.g., '3it94d1ivx' )
    ts TEXT NOT NULL,       -- 時間戳記字串 ( e.g., '260619-0218' )
    content TEXT NOT NULL   -- 含有 <li> 的原始 HTML 內容
)
CREATE TABLE "plurk_tag" (
    plurk_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    PRIMARY KEY (plurk_id, tag),
    FOREIGN KEY (plurk_id) REFERENCES plurk(id) ON DELETE CASCADE
)
```

## 2. 蒐集 rss、 轉成 html

1. 定期下載 rss： 在 crontab 裡加一句：
   wget http://www.plurk.com/ckhung0.xml -O $HOME/plurklogs/$(date '+%y%W').xml
   以上採用我的噗浪 id "ckhung0" 並假設已先建好 $HOME/plurklogs/ 目錄。
   我的 cron 設定是每週檢查一次 xml。
2. 蒐集許多 xml 之後：
    for f in \*.xml ; do xq-python . $f > ${f/%xml/json} ; done
    ./prj2html.py \*.json > new.html 
   最後編輯 html 檔， 手動加入 new.html 並刪除重複的部分， 得到 2?.html 這樣的內容。
   詳見： [噗浪 rss 備份： 轉成 json 再轉 html](https://newtoypia.blogspot.com/2021/09/xml-js-jq-rss.html)。

## 3. 把網頁版噗文匯入資料庫

更新過 2?.html 之後： `./h2db 2?.html` 把網頁版噗文匯入資料庫 plurk_tags.db。
可重複執行， 若遇相同的 id， 新的會蓋掉舊的。

## 4. 準備提示詞相關檔案

以下假設你已有 deepinfra 的帳號與 API key。
請先查看/修改 llm-tag.md 與 tag-hierarchy.yaml 的內容。

```
TP_SRC=.../tagging-plurk
WORKDIR=$HOME/tp-work
mkdir -p $WORKDIR

export OPENAI_BASE_URL=https://api.deepinfra.com/v1/openai
export OPENAI_API_KEY=$(< 金鑰檔路徑)

cd $TP_SRC
cat llm-tag.md tag-hierarchy.yaml > $WORKDIR/cached-prompt.txt
printf '\n===== plurk-list.txt =====\n' >> $WORKDIR/cached-prompt.txt
```

從資料庫裡匯出所有噗文、 刪除 html 標籤及多餘的字串 (例如每一噗首的使用者 id)：
sqlite3 -separator ' ' plurk_tags.db 'select id,content from plurk order by ts asc' | \
    perl -pe 's#</?\w[^>]\*>##g; s#(\d{6}-\d{4})\s+(ckhung0)?\s+#$1 %% #' > $WORKDIR/plurk-list.txt
<!--
間隔挑選一些噗文， 實驗用：
perl -ne 'print if ($.%79==12)' $WORKDIR/plurk-list.txt > /tmp/plurk-list.txt
-->

切割檔案， 一次只處理一小批：
```
cd $WORKDIR
mkdir -p ds
split -l 30 -d -a 3 plurk-list.txt
```

## 4. 呼叫 LLM 下標籤

```
date
for f in x??? ; do
    echo "$f "
    time ./llm-query.py -m deepseek-ai/DeepSeek-V4-Flash --prompt-cache-key 'tagging-plurk' -d '###' -s cached-prompt.txt -u $f > ds/$f.txt
done
date
```

## 5. 後續整理標籤、 匯入資料庫

對每一噗刪除以下的標籤： 重複、 祖先、 不在 tag-hierarchy.yaml 內
```
./cleanup-llm-tag.py -t tag-hierarchy.yaml ds/x???.txt | \
    perl -nale 'for $t (@F[3..$#F]) { print "$F[0],$t" if $F[1]=~/^\d{6}-\d{4}$/ }' > pt.txt
```
檢查有無重複： `sort pt.txt | uniq -c | sort -n | tail`

進入 litecli 或 sqlite3 將標籤匯入資料庫 plurk_tags.db：
```
.mode csv
.import pt.txt plurk_tag
```

