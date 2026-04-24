# Curls de referencia — BrightData DCA triggers

Comandos de prueba para disparar cada scraper directamente contra la API DCA de BrightData.
Reemplazar `$BRIGHTDATA_API_KEY` con el valor del `.env`.

---

## cosme
```bash
curl -H "Authorization: Bearer $BRIGHTDATA_API_KEY" \
     -H "Content-Type: application/json" \
     -d '[{"url":"https://www.cosme.net/bestcosme/archive/2025/grand/","category":"skincare","crawl_limit":10}]' \
     "https://api.brightdata.com/dca/trigger?collector=c_mo7zv65x2914uyi2n4&queue_next=1"
```

## indiamart
```bash
curl -H "Authorization: Bearer $BRIGHTDATA_API_KEY" \
     -H "Content-Type: application/json" \
     -d '[{"url":"https://dir.indiamart.com/impcat/caustic-soda.html","kind":"mcat"}]' \
     "https://api.brightdata.com/dca/trigger?collector=c_mo90ehh42wq2ili8&queue_next=1"
```

## made-in-china
```bash
curl -H "Authorization: Bearer $BRIGHTDATA_API_KEY" \
     -H "Content-Type: application/json" \
     -d '[{"url":"https://www.made-in-china.com/Chemicals-Catalog/Alkali.html","max_pages":3,"is_rerun":false}]' \
     "https://api.brightdata.com/dca/trigger?collector=c_mo8p01aj1401mhi4sn&queue_next=1"
```

## alibaba
```bash
curl -H "Authorization: Bearer $BRIGHTDATA_API_KEY" \
     -H "Content-Type: application/json" \
     -d '[{"url":"https://www.alibaba.com/trade/search?SearchText=industrial+chemicals&has4Tab=true","search_keyword":"industrial chemicals","max_pages":5,"supplier_country":"CN","min_price":0,"max_price":5000}]' \
     "https://api.brightdata.com/dca/trigger?collector=c_mnypbnxc1u871q7sgb&queue_next=1"
```

## olive-young
```bash
curl -H "Authorization: Bearer $BRIGHTDATA_API_KEY" \
     -H "Content-Type: application/json" \
     -d '[{"url":"https://global.oliveyoung.com/display/page/best-seller","max_pages":3}]' \
     "https://api.brightdata.com/dca/trigger?collector=c_mob060tkv07mp3ft9&queue_next=1"
```

## nutraingredients (sin middleware — colector huérfano)
```bash
curl -H "Authorization: Bearer $BRIGHTDATA_API_KEY" \
     -H "Content-Type: application/json" \
     -d '[{"url":"https://www.nutraingredients.com/Health-conditions/Beauty-wellness/"}]' \
     "https://api.brightdata.com/dca/trigger?collector=c_mo881p3h23z6ctghqw&queue_next=1"
```

---

## Obtener resultado de un dataset
```bash
curl "https://api.brightdata.com/dca/dataset?id=<SNAPSHOT_ID>" \
     -H "Authorization: Bearer $BRIGHTDATA_API_KEY"
```
