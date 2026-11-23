# মতামত ও সম্পাদকীয় সংগ্রহ | BD Editorials

বাংলাদেশের প্রধান অনলাইন সংবাদপত্রগুলোর **কলাম, মতামত, সম্পাদকীয় ও উপ-সম্পাদকীয়** এক জায়গায় খুঁজে পাওয়া এবং সংক্ষিপ্ত **পাঠক মোডে (Reader Mode)** সারাংশ পড়ার জন্য একটি সম্পূর্ণ বিনামূল্যে চালিত, সার্ভারলেস **GitHub Pages + GitHub Actions** স্ট্যাটিক ওয়েব অ্যাপ।

> **স্বত্ব ও নৈতিকতা (Copyright & Ethics):** এই সাইট কোনো লেখার মালিক নয়; সব স্বত্ব সংশ্লিষ্ট পত্রিকার। এখানে শুধুমাত্র শিরোনাম, লেখক, প্রকাশের সময়, ছোট অংশ (`snippet`: ২৫–৪০ শব্দ), সংক্ষিপ্ত সারাংশ (`summary`: সর্বোচ্চ ১২০ শব্দ) এবং মূল লেখার লিংক সংরক্ষণ ও প্রদর্শন করা হয়। কোনো পত্রিকার পূর্ণ লেখা কখনো কপি, ক্যাশ বা সংরক্ষণ করা হয় না।

---

## সূচিপত্র | Contents
1. [বৈশিষ্ট্য (Features)](#১-বৈশিষ্ট্য--features)
2. [আর্কিটেকচার ও ফোল্ডার স্ট্রাকচার (Architecture)](#২-আর্কিটেকচার-ও-ফোল্ডার-স্ট্রাকচার)
3. [পূর্ণাঙ্গ ২৬টি সোর্স অডিট: যাচাইকৃত RSS, Selector ও সীমাবদ্ধতার নোট](#৩-পূর্ণাঙ্গ-২৬টি-সোর্স-অডিট-যাচাইকৃত-rss-selector-ও-নোট)
4. [লোকাল সেটআপ ও চালানোর নিয়ম (Local Setup - বাংলা ও English)](#৪-লোকাল-সেটআপ-ও-চালানোর-নিয়ম--local-setup)
5. [কোড না বদলিয়ে নতুন পত্রিকা যোগ করার নিয়ম (Adding a New Source)](#৫-কোড-না-বদলিয়ে-নতুন-পত্রিকা-যোগ-করার-নিয়ম)
6. [GitHub Pages ও Actions চালু করার নিয়ম (Deployment Guide)](#৬-github-pages-ও-actions-চালু-করার-নিয়ম)
7. [Android APK তৈরি করার নিয়ম (Cloud ও Local APK Build)](#৭-android-apk-তৈরি-করার-নিয়ম--building-android-apk)

---

## ১. বৈশিষ্ট্য | Features

- **৪৭টি বাংলাদেশি পত্রিকার কনফিগারেশন (`sources.yml`):** ৩৯টি বাংলা ও ৮টি ইংরেজি পত্রিকা (`bdnews24-bn` এবং `bdnews24-en` দুটি সম্পূর্ণ আলাদা সোর্স ও আলাদা কনফিগ হিসেবে যুক্ত)। এর মধ্যে **৪০টি সক্রিয় সোর্স** থেকে লাইভ ডেটা সংগৃহীত হচ্ছে এবং ৭টি ব্লকড/অফলাইন সোর্স স্বচ্ছভাবে নথিভুক্ত।
- **স্বয়ংক্রিয় সংগ্রহ (Every 3 Hours):** GitHub Actions cron (`0 */3 * * *`) প্রতি ৩ ঘণ্টায় নতুন মতামত ও সম্পাদকীয় সংগ্রহ করে।
- **কপিরাইট-বান্ধব সারাংশ (`scraper/summarize.py`):**
  - প্রথমে `og:description` / meta description পরীক্ষা করে (`>= ৮০` শব্দ হলে সর্বোচ্চ ১২০ শব্দে সীমিত রাখে)।
  - তা ছোট হলে পূর্ণ লেখা কেবল মেমোরিতে রেখে একাধিক অনুচ্ছেদ থেকে গুরুত্বপূর্ণ বাক্য বাছাই করে ৮০–১২০ শব্দের **extractive সারাংশ** তৈরি করে (বাংলা `।`, `?`, `!` বাক্য-বিভাজন সাপোর্টসহ) এবং সাথে সাথে মেমোরি থেকে মূল লেখা মুছে ফেলে।
  - ঐচ্ছিকভাবে GitHub Secrets-এ `GEMINI_API_KEY` বা `OPENAI_API_KEY` থাকলে AI সারাংশ তৈরি করে, না থাকলে স্বয়ংক্রিয়ভাবে extractive পদ্ধতিতে fallback করে।
- **পাঠক মোড (Reader Mode):**
  - মোবাইলে full-screen sheet ও ডেস্কটপে ড্রয়ার প্যানেল (`#/read/<id>` ডিপ-লিংকসহ)।
  - `Noto Serif Bengali` টাইপোগ্রাফি, `A−` / `A+` ফন্ট সাইজ নিয়ন্ত্রণ, **Light / Sepia / Dark** থিম, সারাংশের শব্দসংখ্যা ও পদ্ধতি ব্যাজ, ক্লিকযোগ্য টপিক ট্যাগ, সোয়াইপ ও কিবোর্ড শর্টকাট (`Esc`, `←`, `→`) এবং **"পূর্ণ লেখা মূল সাইটে পড়ুন →"** বাটন।
- **ফিল্টার, সার্চ ও লেখক ডিরেক্টরি/পেজ:**
  - পত্রিকা (multi-select, ভাষা অনুযায়ী ফিল্টার ও আর্টিকেল সংখ্যা ব্যাজসহ), ধরন (সম্পাদকীয়, উপ-সম্পাদকীয়, কলাম, মতামত, বিশ্লেষণ), ভাষা (বাংলা / English) ও তারিখের রেঞ্জ ফিল্টার।
  - বাংলা ইউনিকোড ও Fuse.js ভিত্তিক ক্লায়েন্ট-সাইড ফুল-টেক্সট সার্চ।
  - আলাদা **লেখকবৃন্দ (`#/authors`)** ডিরেক্টরি এবং যেকোনো লেখকের নামের ওপর ক্লিক করলে ওই লেখকের প্রোফাইল ও সব সংগৃহীত লেখার পেজ (`#/author/<name>`)।
- **আজকের সম্পাদকীয়:** সব পত্রিকার সর্বশেষ সম্পাদকীয় পাশাপাশি তুলনা করে পড়ার আলাদা ট্যাব (`#/editorials`)।
- **অফলাইন PWA, বুকমার্ক ও নিজস্ব RSS:** `localStorage`-এ "পরে পড়ব" বুকমার্ক, অফলাইন সার্ভিস ওয়ার্কার (`sw.js`), বাংলা/ইংরেজি সংখ্যা টগল এবং আউটবাউন্ড `feed.xml`।
- **নির্ভরযোগ্যতা ও আর্কাইভিং:**
  - প্রতিটি সোর্স আলাদা `try/except` ব্লকে চলে, `robots.txt` ও প্রতি ডোমেইনে ২–৩ সেকেন্ড বিরতি মেনে চলে।
  - ৯০ দিনের পুরনো লেখা স্বয়ংক্রিয়ভাবে `data/archive/YYYY-MM.json`-এ স্থানান্তরিত হয়।
  - টানা ৩ বার কোনো সোর্স ব্যর্থ হলে স্বয়ংক্রিয়ভাবে GitHub Issue তৈরি হয় এবং `data/health.json`-এ স্ট্যাটাস সংরক্ষিত থাকে।

---

## ২. আর্কিটেকচার ও ফোল্ডার স্ট্রাকচার

```text
/
├─ sources.yml                  # সব ২৬টি পত্রিকার কনফিগারেশন (RSS / CSS selectors)
├─ requirements.txt             # Python 3.11+ ডিপেন্ডেন্সি
├─ pyproject.toml               # pytest ও প্রজেক্ট কনফিগ
├─ scraper/
│  ├─ main.py                   # থ্রেড-সেফ অর্কেস্ট্রেটর, চ্যাঙ্কার ও হেলথ ট্র্যাকার
│  ├─ http_client.py            # robots.txt যাচাই, ২-৩ সেকেন্ড domain delay ও backoff
│  ├─ normalize.py              # URL canonicalization, SHA-256 ID, বাংলা তারিখ ও ক্যাটাগরি
│  ├─ dedupe.py                 # ডুপ্লিকেট দূরীকরণ ও ৯০ দিনের মাসিক আর্কাইভিং
│  ├─ summarize.py              # মেটা / এক্সট্রাক্টিভ / ঐচ্ছিক AI সারাংশ (<= ১২০ শব্দ)
│  ├─ rss_builder.py            # আউটবাউন্ড web/feed.xml জেনারেটর
│  ├─ fetchers/                 # rss.py এবং html.py
│  ├─ parsers/                  # generic.py এবং prothom_alo.py (Quintype SSR parser)
│  └─ tests/                    # pytest ইউনিট টেস্ট (১২টি টেস্ট) ও HTML fixtures
├─ data/
│  ├─ articles.json             # সক্রিয় লেখা (<= ৯০ দিন)
│  ├─ chunks/                   # Infinite scroll-এর জন্য page-1.json, manifest.json ইত্যাদি
│  ├─ archive/                  # মাসভিত্তিক আর্কাইভ (YYYY-MM.json)
│  ├─ sources.json              # ফ্রন্টএন্ডের জন্য সোর্স মেটাডেটা
│  └─ health.json               # প্রতিটি সোর্সের শেষ সফল fetch ও error লগ
├─ web/                         # ভ্যানিলা HTML/CSS/JS ফ্রন্টএন্ড, ২৬টি SVG লোগো, PWA ও sw.js
└─ .github/workflows/           # scrape.yml (প্রতি ৩ ঘণ্টায়) ও deploy.yml (GitHub Pages)
```

---

## ৩. পূর্ণাঙ্গ ২৬টি সোর্স অডিট: যাচাইকৃত RSS, Selector ও নোট

প্রতিটি সাইটের আসল পেজ ও `robots.txt` সরাসরি পরীক্ষা করে নিচের কনফিগারেশন নির্ধারণ করা হয়েছে:

### বাংলা পত্রিকা (১৭টি)

| সোর্স ID | পত্রিকা | অবস্থা | পদ্ধতি | যাচাইকৃত Feed / URL ও CSS Selectors | অডিট নোট ও অনিশ্চয়তা |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `prothom-alo` | প্রথম আলো | সচল | `html` (`prothom_alo`) | `https://www.prothomalo.com/opinion` → `script#static-page` | `/stories.rss`-এ সাধারণ সংবাদ থাকে; `/opinion`-এর Quintype SSR JSON থেকে লেখক, বিভাগ, ছবি ও পাঠ্য সংগৃহীত। |
| `samakal` | সমকাল | সচল | `html` | `/opinion`, `/editorial` → `.DCatLead a, .Catcards a` • Author: `div.writter p` • Body: `div.dNewsDesc p` | `/rss.xml` HTML 404 দেয়; যাচাইকৃত HTML selector ব্যবহৃত। |
| `ittefaq` | দৈনিক ইত্তেফাক | সচল | `rss` | RSS: `https://www.ittefaq.com.bd/feed/opinion` • Body: `div.jw_article_body p` | অফিসিয়াল RSS ফিড সক্রিয়, মতামত ও সম্পাদকীয় লেখকসহ আসে। |
| `dhaka-post` | ঢাকা পোস্ট | সচল | `html` | `/opinion` → `a[href*='/opinion/']` (`/opinion/\d+`) • Author: `meta[name='author']` | যাচাইকৃত HTML ও OpenGraph/meta ট্যাগ। |
| `bdnews24-bn` | বিডিনিউজ২৪ বাংলা | সচল | `html` | `https://bangla.bdnews24.com/opinion` → `.Cat-lead-wrapper a, .Cat-list a` (`[a-z0-9]{10}$`) • Author: `.detail-author-name a` • Body: `div.details-brief p` | আলাদা বাংলা সোর্স (`id: bdnews24-bn`, `language: bn`); `/rss.xml` HTML দেয় বলে যাচাইকৃত HTML ব্যবহৃত। |
| `bangla-tribune` | বাংলা ট্রিবিউন | সচল | `rss` | RSS: `/feed/columns`, `/feed/others/opinion` • Body: `div.jw_article_body p` | অফিসিয়াল কলাম ও মতামত RSS ফিড সক্রিয়। |
| `naya-diganta` | নয়া দিগন্ত | সচল | `html` | `/category/editorial/52`, `/category/op-ed/53`, `/category/opinion/14` → `.pd-byline-left > span:first-child` • Body: `article.pd-body p` | `www.` সাবডোমেইনে SSL mismatch থাকায় মূল ডোমেইন `dailynayadiganta.com` ব্যবহৃত; সম্পাদকীয়, উপ-সম্পাদকীয় ও মতামত তিন বিভাগই যুক্ত। |
| `manabzamin` | মানবজমিন | সচল | `html` | `/category/মত-মতান্তর`, `/category/প্রবন্ধ` → `span.font-medium` • Body: `div.prose p` | মত-মতান্তর ও প্রবন্ধ বিভাগ থেকে লেখকসহ সংগৃহীত। |
| `jugantor` | যুগান্তর | সচল | `rss` (XML Sitemap) | `https://www.jugantor.com/news_sitemap.xml` (`jugantor.com/viewers-opinion/\d+`) | HTML পেজে Cloudflare JS challenge (HTTP 403) থাকলেও `robots.txt`-এ উন্মুক্ত অফিসিয়াল Google News XML ফিড থেকে মতামত ইনডেক্স করা হচ্ছে। |
| `bd-pratidin` | বাংলাদেশ প্রতিদিন | সচল | `rss` | `https://www.bd-pratidin.com/rss.xml` (`bd-pratidin.com/editorial/\d{4}/`) | HTML পেজে Cloudflare 403 আসায় অফিসিয়াল `/rss.xml` ফিড থেকে `/editorial/` লেখাগুলো সংগৃহীত হচ্ছে। |
| `janakantha` | জনকণ্ঠ | সচল | `html` | `/opinion` → `.DCatTopNews a, .DCatTopNewsList a` • Date: `p.date` | `/rss.xml` 404 দেয়; যাচাইকৃত HTML selector ব্যবহৃত। |
| `bonik-barta` | বণিক বার্তা | সচল | `html` | `https://bonikbarta.com/editorial` → `h3 a[href*='/editorial/']` • Body: `div.prose p` | `/editorial`-এ সম্পাদকীয় ও নীতি-আলোচনা উপসম্পাদকীয় উভয়ই থাকে। |
| `sangbad` | সংবাদ | সচল | `html` | `https://sangbad.net/opinion/`, `/editorial/` → `a.prothom-songbad-post-style` • Body: `div.story-details p` | `sangbad.net.bd` রিডাইরেক্ট হয়ে `sangbad.net`-এ যায়; সাইডবারের সাধারণ খবর বাদ দিতে `a.prothom-songbad-post-style` নির্দিষ্ট করা হয়েছে। |
| `inqilab` | দৈনিক ইনকিলাব | সচল | `html` | `/editorial` → `a[href*='/editorial/article/'], a[href*='/editorial/news/']` • Body: `div.description p` | যাচাইকৃত HTML selector ব্যবহৃত। |
| `kaler-kantho` | কালের কণ্ঠ | **ব্লকড (`disabled`)** | `html` | `https://www.kalerkantho.com/print-edition/sub-editorial` | HTML, `/rss.xml` এবং `/sitemap.xml`—সব এন্ডপয়েন্টেই Cloudflare Turnstile (`HTTP 403, cf-mitigated: challenge`) সক্রিয়। |
| `jago-news-24` | জাগো নিউজ ২৪ | **ব্লকড (`disabled`)** | `html` | `https://www.jagonews24.com/opinion` | `/opinion`, `/rss/opinion.xml` এবং আর্টিকেল পেজে Cloudflare challenge (`HTTP 403`) সক্রিয় (`/rss/rss.xml`-এ মতামত থাকে না)। |
| `amader-shomoy` | আমাদের সময় | **নিষ্ক্রিয় (`disabled`)** | `html` | `https://www.dainikamadershomoy.com/category/all/opinion` | Client-side Nuxt SPA (`__NUXT__`); HTML-এ কোনো আর্টিকেল লিংক নেই এবং API সাবডোমেইন `/api.dainikamadershomoy.com/` সাইটের `robots.txt`-এ নিষিদ্ধ (`Disallow`)। |

### English Newspapers (৯টি)

| সোর্স ID | পত্রিকা | অবস্থা | পদ্ধতি | যাচাইকৃত Feed / URL ও CSS Selectors | অডিট নোট ও অনিশ্চয়তা |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `daily-star` | The Daily Star | সচল | `rss` | RSS: `/opinion/rss.xml`, `/opinion/editorial/rss.xml`, `/opinion/views/rss.xml` • Author: `.block-author-info-block a[href*='/author/']` • Body: `span.text-formatted p` | অফিসিয়াল Drupal RSS ফিড সক্রিয়। |
| `dhaka-tribune` | Dhaka Tribune | সচল | `rss` | RSS: `https://www.dhakatribune.com/feed/opinion` • Author: `div.each_author a.name` • Body: `div.jw_article_body p` | অফিসিয়াল RSS ফিডে Op-Ed, Editorial ও Longform কভার হয়। |
| `tbs` | The Business Standard | সচল | `rss` | RSS: `https://www.tbsnews.net/thoughts/rss.xml` • Author: `div.author-name a` • Body: `div.section-content p` | TBS Thoughts সেকশনের অফিসিয়াল RSS ফিড। |
| `new-age` | New Age | সচল | `html` | `/articlelist/55/Editorial`, `/articlelist/54/Opinion` → `h3 a[href*='/post/']` • Author: `a.d-inline-flex` • Body: `div.post-content p` | টেমপ্লেটে ভুল `datetime="2026-07-06"` হার্ডকোড থাকায় দৃশ্যমান `<time>` টেক্সট থেকে সঠিক তারিখ নেওয়া হয়। |
| `financial-express` | The Financial Express | সচল | `html` | `/category/views/views`, `/category/editorial`, `/category/views/columns`, `/category/views/opinions` → `h2 a, h3 a` | `/feed` 404 দেয়; যাচাইকৃত ৪টি ক্যাটাগরি পেজ যুক্ত। |
| `daily-observer` | The Daily Observer | সচল | `html` | `/menu/246` (Opinion), `/menu/199` (Editorial) → `div.title_inner a[href*='news/']` • Date: `div.pub` • Body: `div.mood` | আর্টিকেল বডি `<p>`-এর বদলে `<br>`-বিভাজিত `div.mood`-এ থাকে, যা পার্সারে সাপোর্ট করা হয়েছে। |
| `bdnews24-en` | bdnews24 English | সচল | `html` | `https://bdnews24.com/opinion` → `.Cat-lead-wrapper a, .Cat-list a` (`//bdnews24\.com/opinion/[a-z0-9]{10}$`) • Author: `.detail-author-name a` • Body: `div.details-brief p` | সম্পূর্ণ আলাদা ইংরেজি সোর্স (`id: bdnews24-en`, `language: en`)। |
| `daily-sun` | Daily Sun | **ব্লকড (`disabled`)** | `html` | `https://www.daily-sun.com/opinion` | `/opinion` ও `/rss.xml`-এ Cloudflare anti-bot challenge (`HTTP 403`) সক্রিয়। |
| `the-independent` | The Independent | **অফলাইন (`disabled`)** | `html` | `https://www.theindependentbd.com` | প্রকাশনা বন্ধ / সার্ভার সংযোগ টাইম-আউট (`Connection timed out`)। |
| `bangladesh-post` | Bangladesh Post | সচল | `html` | `/categories/editorial`, `/categories/opinion` → `div.box-body a[href*='/posts/']` • Body: `div.post-details-content p` | `allbanglanewspaper.xyz` থেকে যুক্ত ইংরেজি দৈনিক। |

### অতিরিক্ত সংযোজিত পত্রিকা (`allbanglanewspaper.xyz` থেকে যাচাইকৃত ২০টি বাংলা সোর্স)

| সোর্স ID | পত্রিকা | অবস্থা | পদ্ধতি | যাচাইকৃত Feed / URL ও CSS Selectors |
| :--- | :--- | :--- | :--- | :--- |
| `ajker-patrika` | আজকের পত্রিকা | সচল | `html` | `/op-ed` → `a[href*='/op-ed/']` • Body: `div.block-full_richtext p` |
| `desh-rupantor` | দেশ রূপান্তর | সচল | `rss` | Official RSS: `https://www.deshrupantor.com/feed/opinion` • Body: `div.jw_article_body p` |
| `bhorer-kagoj` | ভোরের কাগজ | সচল | `html` | `/editorial`, `/thinking` → `a.linkOverlay` • Body: `div.detailBody p` |
| `daily-sangram` | দৈনিক সংগ্রাম | সচল | `html` | `/opinion/` → `a[href*='/opinion/column/'], a[href*='/opinion/editorial/']` • Author: `div.post-writer a` |
| `protidiner-sangbad` | প্রতিদিনের সংবাদ | সচল | `html` | `/todays-newspaper/uposompadokio`, `/muktomot` → `div.dtl_section p` |
| `amar-sangbad` | আমার সংবাদ | সচল | `html` | `/opinion` → `a[href*='/opinion/news/']` • Body: `article.content-details p` |
| `alokito-bangladesh` | আলোকিত বাংলাদেশ | সচল | `html` | `/openion` → `.lead_content a, .content_list a` • Body: `div.dtl_content_block p` |
| `shomoyer-alo` | সময়ের আলো | সচল | `html` | `/menu/295` → `div.title_lead a, div.title_body a` • Body: `div.mood` |
| `dainik-bangla` | দৈনিক বাংলা | সচল | `html` | `/opinion` → `a[href*='/opinion/']` • Body: `div.news_body p` |
| `bangladesher-khabor` | বাংলাদেশের খবর | সচল | `html` | `/opinion` → `div.caption a[href*='/opinion/']` |
| `share-biz` | শেয়ার বিজ | সচল | `html` | `/daily/editorial` → `.DCatTopNews a, .DSubCategoryTopNewsList a` • Author: `div.writter` |
| `suprobhat` | সুপ্রভাত বাংলাদেশ | সচল | `rss` | Official RSS: `/category/opinion/feed/`, `/category/opinion/editorial/feed/` |
| `banglanews24` | বাংলানিউজ২৪ | সচল | `html` | `/category/opinion` → `a[href*='/opinion/news/bd/']` |
| `sarabangla` | সারাবাংলা | সচল | `rss` | Official RSS: `/opinion/feed/`, `/free-opinion/feed/` • Body: `div.sb-single-post-content p` |
| `daily-bangladesh` | ডেইলি বাংলাদেশ | সচল | `html` | `/opinion`, `/views` → `div.details-body p` |
| `bartabazar` | বার্তাবাজার | সচল | `rss` | Official RSS: `/news/category/মতামত/feed/` • Body: `div.post-content p` |
| `dainik-azadi` | দৈনিক আজাদী | সচল | `rss` | Official RSS: `/category/today-newspaper/editorial/feed/` • Body: `div.td-post-content p` |
| `karatoa` | দৈনিক করতোয়া | সচল | `html` | `/category/editorial` → `a[href*='/article/']` • Body: `div.dtl_content_section p` |
| `kalbela` | কালবেলা | **ব্লকড (`disabled`)** | `html` | Cloudflare anti-bot challenge (`HTTP 403, cf-mitigated: challenge`) সক্রিয়। |
| `risingbd` | রাইজিংবিডি | **ব্লকড (`disabled`)** | `html` | Cloudflare anti-bot challenge (`HTTP 403, cf-mitigated: challenge`) সক্রিয়। |

---

## ৪. লোকাল সেটআপ ও চালানোর নিয়ম | Local Setup

```bash
# ১. ভার্চুয়াল এনভায়রনমেন্ট ও ডিপেন্ডেন্সি ইনস্টল
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

# ২. ইউনিট টেস্ট চালান
pytest -v

# ৩. সব সক্রিয় সোর্স স্ক্র্যাপ করুন (অথবা নির্দিষ্ট সোর্স: --sources bdnews24-bn,tbs)
python -m scraper.main --max-per-source 8

# ৪. লোকাল ব্রাউজারে দেখুন
python -m http.server 8000
```
ব্রাউজারে খুলুন: **`http://localhost:8000/web/`**

---

## ৫. কোড না বদলিয়ে নতুন পত্রিকা যোগ করার নিয়ম

`sources.yml` ফাইলে নতুন একটি ব্লক যোগ করলেই স্ক্র্যাপার ও ফ্রন্টএন্ড স্বয়ংক্রিয়ভাবে তা যুক্ত করে নেবে:

```yaml
  - id: example-paper
    name_bn: "উদাহরণ পত্রিকা"
    name_en: "Example Paper"
    language: bn
    enabled: true
    logo: "assets/logos/prothom-alo.svg"
    website: "https://example.com"
    section_url: "https://example.com/opinion"
    fetch_method: html          # অফিসিয়াল RSS থাকলে 'rss' দিন এবং rss_urls ব্যবহার করুন
    parser: generic
    default_category: opinion
    min_articles: 3
    max_articles: 10
    selectors:
      item_link: "article a[href*='/opinion/']"
      url_pattern: "/opinion/\\d+"
      title: "meta[property='og:title'], h1"
      author: ".author-name, meta[name='author']"
      published_at: "meta[property='article:published_time'], time"
      body: "article p"
```

---

## ৬. GitHub Pages ও Actions চালু করার নিয়ম (Deployment Guide)

1. রিপোজিটরিটি GitHub-এর `main` ব্রাঞ্চে push করুন।
2. **Settings → Pages → Build and deployment → Source** থেকে **`GitHub Actions`** নির্বাচন করুন।
3. **Settings → Actions → General → Workflow permissions** থেকে **`Read and write permissions`** সক্রিয় করুন।
4. *(ঐচ্ছিক)* **Settings → Secrets and variables → Actions**-এ `GEMINI_API_KEY` বা `OPENAI_API_KEY` যোগ করতে পারেন (না থাকলে বিনামূল্যে extractive সারাংশ ব্যবহৃত হবে)।
5. **Actions** ট্যাবে গিয়ে **"Scrape & Update Editorials"** ওয়ার্কফ্লোতে **`Run workflow`** চাপুন।

---

## ৭. Android APK তৈরি করার নিয়ম | Building Android APK

এই অ্যাপটি থেকে ইনস্টলযোগ্য **Android APK (`bd-editorials.apk`)** তৈরি করা যাবে। APK-তে আপনার লাইভ **GitHub Pages ডেটা লিংক** স্বয়ংক্রিয়ভাবে যুক্ত থাকে—ফলে অ্যাপটি ইনস্টল করার পরও **প্রতি ৩ ঘণ্টায় নতুন সংগৃহীত লেখা স্বয়ংক্রিয়ভাবে অ্যাপে চলে আসবে**, এবং ইন্টারনেট না থাকলে অফলাইন ক্যাশ থেকে চলবে।

### পদ্ধতি ১: GitHub Actions দিয়ে ক্লাউডে ১-ক্লিকে APK বিল্ড (প্রস্তাবিত — পিসিতে Android Studio লাগবে না)

1. রিপোজিটরিটি GitHub-এ push করার পর **Actions** ট্যাবে যান।
2. বাম পাশের তালিকা থেকে **"Build Android APK"** ওয়ার্কফ্লো সিলেক্ট করে **`Run workflow`** চাপুন।
3. ২–৩ মিনিটের মধ্যে বিল্ড শেষ হলে ওই রানের নিচে **Artifacts** অংশ থেকে **`bd-editorials-apk`** ডাউনলোড করে `.zip` আনজিপ করলেই `bd-editorials.apk` পেয়ে যাবেন।
4. *(ঐচ্ছিক Release APK)* ভার্সন ট্যাগ পুশ করলে (`git tag v1.0.0 && git push origin v1.0.0`) সরাসরি রিপোজিটরির **Releases** পেজে `bd-editorials.apk` যুক্ত হয়ে যাবে।

### পদ্ধতি ২: লোকাল কম্পিউটারে APK বিল্ড (Node.js + JDK 21 + Android SDK প্রয়োজন)

```powershell
# ১. Capacitor প্যাকেজ ইনস্টল
npm install

# ২. আপনার GitHub Pages লাইভ ডেটা URL সেট করে বান্ডেল প্রস্তুত করুন
$env:REMOTE_DATA_URL = "https://<YOUR_GITHUB_USERNAME>.github.io/<YOUR_REPO_NAME>/data"
.\.venv\Scripts\python.exe scripts\prepare_apk_www.py

# ৩. Android প্রজেক্ট তৈরি ও সিঙ্ক করুন
npx cap add android
npx cap sync android

# ৪. Gradle দিয়ে APK বিল্ড করুন
cd android
.\gradlew.bat assembleDebug
# তৈরি হওয়া APK পাবেন এখানে:
# android\app\build\outputs\apk\debug\app-debug.apk
```
