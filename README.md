# Trakt-to-Bangumi
从Trakt迁移至Bangumi / 导出Trakt记录到Bangumi / CSV文件格式转换

### 预览
<img src="https://github.com/user-attachments/assets/6f37e343-b7ab-4a82-8cb7-0c50a5787a99" width="800px">

<img src="https://github.com/user-attachments/assets/20154748-2114-48b1-8089-fdcbef4f24eb" width="800px">
<img src="https://github.com/user-attachments/assets/1b2a6446-a331-4635-8058-b573df9c5f2e" width="800px">
<img src="https://github.com/user-attachments/assets/bccd61ed-90d6-4da9-ba35-29e36f4a2d38" width="800px">


## 方案：

使用[trakt](https://github.com/xbgmsharp/trakt)项目导出Trakt历史或列表为CSV文件 → 使用本项目转换CSV格式内容为Bangumi支持的格式内容 ~~→ 使用[Bangumi2Bangumi](https://github.com/Adachi-Git/Bangumi2Bangumi)项目的“Csv版”将CSV导入Bangumi~~ → 使用本项目改良版BangumiMigrate-Csv-Pro.py将CSV一键导入Bangumi（如果觉得好用请去给[原项目](https://github.com/Adachi-Git/Bangumi2Bangumi)星星）

### 你需要准备的：
* Python环境
* [TMDB API 密钥](https://www.themoviedb.org/settings/api)（注册登录任意申请）（我暂时提供此API）
* [Trakt API Client ID](https://trakt.tv/oauth/applications)（任意创建）
* [Bangumi API 访问令牌](https://next.bgm.tv/demo/access-token)（任意创建）

## 开始使用
* Python安装本项目所需库
```
pip install requests pandas python-dateutil simplejson chardet
```

* 使用[trakt](https://github.com/xbgmsharp/trakt)项目将Trakt历史或列表导出为CSV（导出文档：https://github.com/xbgmsharp/trakt/blob/master/export.md ）

* 导出历史列表中的所有Shows（剧集）为export_shows_history.csv：
```
python export_trakt.py -c config.ini -t shows -o export_shows_history.csv -l history
```
* 导出历史列表中的所有Movies（电影）为export_movies_history.csv：
```
python export_trakt.py -c config.ini -t movies -o export_movies_history.csv -l history
```
* 导出观看列表中所有Shows（剧集）为export_shows_watchlist.csv：
```
python export_trakt.py -c config.ini -t shows -o export_shows_watchlist.csv -l watchlist
```
* 导出观看列表中所有Movies（电影）为export_movies_watchlist.csv：
```
python export_trakt.py -c config.ini -t movies -o export_movies_watchlist.csv -l watchlist
```

* 将导出后的文件放到本项目文件夹下并按照要求修改config.ini配置文件，已经标注了必填项和建议填写项

>  [!NOTE]
> 注意本项目暂时不支持多个同时转换，请按需一个一个文件转换

* 启动``Trakt-to-Bangumi.py``开始转换，然后耐心等待（内容为实时写入如有不便可退出，也支持当天续写）
* 转换完后如果未修改过输出文件名直接启动``BangumiMigrate-Csv-Pro.py``即可开始导入至Bangumi，如有修改输出名请修改配置文件中对应导入项

#### 本项目生成文件说明
本项目总共会生成文件``3``个
* `bangumi_export.csv`：转换后的文件
* `failure_log_20250×0×.csv`：条目匹配失败日志
* `success_log_20250×0×.csv`：条目匹配成功日志

<ins>_另外需要注意本项目尚未做归档文件功能，如果有旧同名文件会在同名文件里面接着生成，请注意自行备份迁移_</ins>


## 拓展功能
### dedup.py
> Bangumi-to-Trakt 、 Trakt-to-Bangumi 项目专用去重脚本

#### 功能说明

此功能用来满足定期同步使用或者多次使用用户的需求，通过对导出文件进行去重留新避免每次使用都需要把已有数据重新转换和导入。

原理是把旧的导出文件和新的对比，排除重复的生成新文件实现去重，或者把[反向项目](https://github.com/wan0ge/Bangumi-to-Trakt)的转换文件作为旧文件进行对比去除对面平台已有的条目。

去重是按照首行列值拆分比对的，脚本第68行左右已支持自定义忽略列值检查，可以实现即使观看时间值发生变化也可以被去重，但个别文件列差别过大无法完全兼容，比如本项目在使用模式3时导出的Trakt文件需要拥有tmdb id，否则会因为和反向项目转换文件结构不同所以无法正常去重，解决方法：使用[trakt](https://github.com/xbgmsharp/trakt)项目导出时添加`-f tmdb`选项，如

导出历史列表中的所有Shows（剧集）为export_shows_history.csv并使用tmdb id：
```
python export_trakt.py -c config.ini -t shows -o export_shows_history.csv -l history -f tmdb
```

#### 使用方法

启动并选择模式去重，去重生成的文件文件会标上New+时间戳

使用dedup.py去重时有3个选择模式

`1.自动选择模式`：自动选择dedup文件夹内的文件作为旧文件，然后根据旧文件名字在脚本所在目录寻找对应新文件，去重后会把新文件扔进dedup方便下次作为旧文件使用

>  [!NOTE]
> 第一次使用需要用户手动或运行脚本创建dedup文件夹并把以往导出的CSV文件放入其中，自动选择时新旧文件名差异不能过大（日期和数字任意）

`2.手动选择模式`：手动输入新旧文件路径，支持拖拽，多个旧文件用空格或逗号分隔，去重后不会移动文件

`3.特殊选择模式`：自动选择脚本目录特定新文件，并在兄弟文件夹匹配特定旧文件（使用反向项目对面平台转换后的文件作为旧文件去重）

>  [!NOTE]
> 模式3是特定匹配
> 
> 新文件只会匹配形如Bangumi××××××.csv、export_shows_history.csv、export_movies_history.csv、export_shows_watchlist.csv、export_movies_watchlist.csv、export_episodes_watchlist.csv；
> 
> 旧文件只会匹配形如bangumi_export.csv、trakt_formatted.csv、temp_trakt_formatted.csv；
> 
> 也就是说新文件只会匹配两个项目最开始导出的文件，旧文件只会匹配两个项目最后转换后的文件，且不允许名称差异过大

---

#### 本项目支持的csv文件格式（"imdb"和"trakt"为必须）
```
"imdb","trakt","watched_at","title"
"tt1910272","42285","2025-04-02T14:08:21.000Z","Steins;Gate"
"tt1118804","24724","2025-04-02T14:07:27.000Z","Clannad"
```
#### 本项目转换后的csv文件格式（"制作地区"可以用来筛选非动画类型）
```
ID,类型,中文,日文,放送,排名,评分,话数,看到,状态,标签,我的评价,我的简评,私密,更新时间,制作地区
10380,动画,命运石之门,STEINS;GATE,2011-04-06,,,,,看过,,,,,2025-04-02,Japan
51,动画,CLANNAD,CLANNAD -クラナド-,2007-10-04,,,,,看过,,,,,2025-04-02,Japan
```
## 给小白的详细使用说明
详见反向项目[Bangumi-to-Trakt](https://github.com/wan0ge/Bangumi-to-Trakt#%E7%BB%99%E5%B0%8F%E7%99%BD%E7%9A%84%E8%AF%A6%E7%BB%86%E4%BD%BF%E7%94%A8%E8%AF%B4%E6%98%8E)
