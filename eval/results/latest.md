# Eval results

Encoder `clip-ViT-B-32+sentence-transformers/clip-ViT-B-32-multilingual-v1`, 213 vectors.

## Retrieval (20 topics, Turkish + English)

| Queries | P@3 | hit@3 | MRR@10 |
|---|---|---|---|
| All (40) | 0.933 | 0.950 | 0.953 |
| Turkish (20) | 0.867 | 0.900 | 0.905 |
| English (20) | 1.000 | 1.000 | 1.000 |

## Video

- Right video first: 67% of 6 queries
- Right moment in the compilation video: 80% of 10 queries

## Latency

Median 6.8 ms, p95 7.3 ms per query (text encoding + FAISS search + metadata).

## Score threshold

Top-1 scores of answered queries: 0.273–0.372 (median 0.324); of queries with no match: 0.228–0.281.
A cutoff at 0.283 keeps 89% of correct top hits and hides 100% of no-match queries.

## Per query

| | Lang | Query | P@3 | Top 3 (✓ relevant) |
|---|---|---|---|---|
| retrieval ✓ | tr | karton kutunun içinde kıvrılmış kedi | 1.00 | ✓ cats_in_boxes, ✓ cats_in_boxes, ✓ cats_in_boxes |
| retrieval ✓ | en | a cat curled up inside a cardboard box | 1.00 | ✓ cats_in_boxes, ✓ cats_in_boxes, ✓ cats_in_boxes |
| retrieval ✓ | tr | karda oynayan köpek | 1.00 | ✓ dogs_in_snow, ✓ dogs_in_snow, ✓ dogs_in_snow |
| retrieval ✓ | en | a dog running through deep snow | 1.00 | ✓ dogs_in_snow, ✓ dogs_in_snow, ✓ dogs_in_snow |
| retrieval ✓ | tr | karlı arazide kızıl tilki | 1.00 | ✓ foxes_in_snow, ✓ foxes_in_snow, ✓ foxes_in_snow |
| retrieval ✓ | en | a red fox in a snowy field | 1.00 | ✓ foxes_in_snow, ✓ foxes_in_snow, ✓ foxes_in_snow |
| retrieval ✓ | tr | Kapadokya'da gökyüzünü dolduran sıcak hava balonları | 1.00 | ✓ balloons_cappadocia, ✓ balloons_cappadocia, ✓ balloons_cappadocia |
| retrieval ✓ | en | hot air balloons floating over rocky valleys at sunrise | 1.00 | ✓ balloons_cappadocia, ✓ balloons_cappadocia, ✓ balloons_cappadocia |
| retrieval ✓ | tr | yeşil kayalıklardan dökülen şelale | 1.00 | ✓ waterfalls@38s, ✓ waterfalls, ✓ waterfalls@0s |
| retrieval ✓ | en | a tall waterfall plunging into a gorge | 1.00 | ✓ waterfalls@18s, ✓ waterfalls, ✓ waterfalls@0s |
| retrieval ✗ | tr | sıra sıra renkli lale tarlası | 0.00 | · fireworks@40s, · fireworks, · bosphorus_night |
| retrieval ✓ | en | rows of colorful tulips in a field | 1.00 | ✓ tulip_fields, ✓ tulip_fields, ✓ tulip_fields |
| retrieval ✓ | tr | İstanbul sokağında kırmızı nostaljik tramvay | 1.00 | ✓ trams_istanbul, ✓ trams_istanbul, ✓ trams_istanbul |
| retrieval ✓ | en | an old red tram on a busy pedestrian street | 1.00 | ✓ trams_istanbul, ✓ trams_istanbul, ✓ trams_istanbul |
| retrieval ✓ | tr | eriyen peynirli pizza | 1.00 | ✓ pizza, ✓ pizza, ✓ pizza |
| retrieval ✓ | en | a freshly baked pizza with toppings | 1.00 | ✓ pizza, ✓ pizza, ✓ pizza |
| retrieval ✓ | tr | köpüğünde desen olan bir fincan kahve | 1.00 | ✓ latte_art, ✓ latte_art, ✓ latte_art |
| retrieval ✓ | en | a heart drawn in milk foam on a latte | 1.00 | ✓ latte_art, ✓ latte_art, ✓ latte_art |
| retrieval ✓ | tr | gece gökyüzünde patlayan havai fişekler | 1.00 | ✓ fireworks@18s, ✓ fireworks, ✓ fireworks |
| retrieval ✓ | en | fireworks exploding in the night sky | 1.00 | ✓ fireworks@28s, ✓ fireworks, ✓ fireworks |
| retrieval ✓ | tr | yağmurda şemsiyeyle yürüyen insanlar | 1.00 | ✓ umbrellas_rain, ✓ umbrellas_rain, ✓ umbrellas_rain |
| retrieval ✓ | en | people walking with umbrellas on a rainy day | 1.00 | ✓ umbrellas_rain, ✓ umbrellas_rain, ✓ umbrellas_rain |
| retrieval ✓ | tr | denizin üzerinde gün batımı | 0.67 | ✓ sunset_sea, · bosphorus_night, ✓ sunset_sea |
| retrieval ✓ | en | the sun setting over the ocean | 1.00 | ✓ sunset_sea, ✓ sunset_sea, ✓ sunset_sea |
| retrieval ✓ | tr | kayalık kıyıda bir deniz feneri | 0.67 | ✓ lighthouses, · sunset_sea, ✓ lighthouses |
| retrieval ✓ | en | a lighthouse on a rocky coastline | 1.00 | ✓ lighthouses, ✓ lighthouses, ✓ lighthouses |
| retrieval ✓ | tr | kitap raflarıyla dolu bir kütüphanenin içi | 1.00 | ✓ libraries, ✓ libraries, ✓ libraries |
| retrieval ✓ | en | inside a grand library with tall bookshelves | 1.00 | ✓ libraries, ✓ libraries, ✓ libraries |
| retrieval ✓ | tr | çayırda otlayan atlar | 1.00 | ✓ horses_grazing, ✓ horses_grazing, ✓ horses_grazing |
| retrieval ✓ | en | horses eating grass in a meadow | 1.00 | ✓ horses_grazing, ✓ horses_grazing, ✓ horses_grazing |
| retrieval ✓ | tr | su altında yüzen deniz kaplumbağası | 1.00 | ✓ sea_turtles, ✓ sea_turtles, ✓ sea_turtles |
| retrieval ✓ | en | a green sea turtle swimming over a reef | 1.00 | ✓ sea_turtles, ✓ sea_turtles@24s, ✓ sea_turtles |
| retrieval ✓ | tr | yan yana park edilmiş bisikletler | 1.00 | ✓ parked_bicycles, ✓ parked_bicycles, ✓ parked_bicycles |
| retrieval ✓ | en | a row of bikes locked to a rack | 1.00 | ✓ parked_bicycles, ✓ parked_bicycles, ✓ parked_bicycles |
| retrieval ✓ | tr | gece ışıklarıyla Boğaz Köprüsü | 1.00 | ✓ bosphorus_night, ✓ bosphorus_night, ✓ bosphorus_night |
| retrieval ✓ | en | a suspension bridge lit up at night over the strait | 1.00 | ✓ bosphorus_night, ✓ bosphorus_night, ✓ bosphorus_night |
| retrieval ✓ | tr | Galata Kulesi | 1.00 | ✓ galata_tower, ✓ galata_tower, ✓ galata_tower |
| retrieval ✓ | en | a medieval stone tower with a conical roof above Istanbul | 1.00 | ✓ galata_tower, ✓ galata_tower, ✓ galata_tower |
| retrieval ✗ | tr | susamlı simit | 0.00 | · sea_waves@2s, · fireworks@22s, · waterfalls@0s |
| retrieval ✓ | en | a Turkish sesame bread ring | 1.00 | ✓ simit, ✓ simit, ✓ simit |
| video ✗ | tr | havai fişek gösterisi |  | · sea_waves@2s, ✓ fireworks@22s, · waterfalls@38s |
| video ✓ | en | a fireworks display |  | ✓ fireworks@28s, ✓ fireworks@14s, · sea_waves@2s |
| video ✗ | tr | akan bir şelale |  | · fireworks@22s, ✓ waterfalls@0s, · sea_waves@2s |
| video ✓ | en | water pouring down a waterfall |  | ✓ waterfalls@18s, ✓ waterfalls@0s, · sea_waves@2s |
| video ✓ | tr | kıyıya vuran dalgalar |  | ✓ sea_waves@0s, ✓ sea_waves@0s, · fireworks@22s |
| video ✓ | en | waves washing onto a beach |  | ✓ sea_waves@0s, ✓ sea_waves@16s, · fireworks@22s |
| moments ✓ | tr | sıcak hava balonları |  | ✓ balloons_cappadocia@0s, · waterfalls@40s, · fireworks@38s |
| moments ✗ | en | hot air balloons in the sky |  | · fireworks@38s, · waterfalls@40s, ✓ balloons_cappadocia@0s |
| moments ✓ | tr | tramvay |  | ✓ trams_istanbul@6s, · fireworks@40s, · fireworks@6s |
| moments ✓ | en | a red tram |  | ✓ trams_istanbul@6s, · fireworks@40s, · fireworks@4s |
| moments ✓ | tr | latte art yapılmış kahve |  | ✓ latte_art@12s, · sea_waves@2s, · waterfalls@0s |
| moments ✓ | en | coffee with milk foam art |  | ✓ latte_art@12s, · sea_waves@2s, · waterfalls@38s |
| moments ✗ | tr | deniz feneri |  | · fireworks@22s, ✓ lighthouses@18s, · sea_waves@0s |
| moments ✓ | en | a lighthouse |  | ✓ lighthouses@18s, · fireworks@42s, · sea_waves@10s |
| moments ✓ | tr | deniz kaplumbağası |  | ✓ sea_turtles@24s, · waterfalls@34s, · sea_waves@8s |
| moments ✓ | en | a sea turtle |  | ✓ sea_turtles@24s, · sea_waves@8s, · waterfalls@34s |
| negatives  | tr | fırlatma rampasında uzay mekiği |  | · fireworks@22s, · balloons_cappadocia, · waterfalls@40s |
| negatives  | en | a space shuttle on the launch pad |  | · fireworks@44s, · fireworks, · balloons_cappadocia |
| negatives  | tr | ameliyathanede çalışan cerrahlar |  | · trams_istanbul, · libraries, · waterfalls@0s |
| negatives  | en | surgeons operating in a hospital |  | · libraries, · parked_bicycles, · libraries |
| negatives  | tr | satranç oynayan iki kişi |  | · umbrellas_rain, · trams_istanbul, · libraries |
| negatives  | en | a crowded subway car during rush hour |  | · trams_istanbul, · fireworks@40s, · trams_istanbul |
