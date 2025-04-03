# Trakt-to-Bangumi
从Trakt迁移至Bangumi / 导出Trakt记录到Bangumi / CSV文件格式转换


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
pip install requests pandas
```

* 使用[trakt](https://github.com/xbgmsharp/trakt)项目将Trakt历史或列表导出为CSV（导出文档：https://github.com/xbgmsharp/trakt/blob/master/export.md ）

* 导出历史列表中的所有Shows（剧集）为export_shows_history.csv：
```
export_trakt.py -c config.ini -t shows -o export_shows_history.csv -l history
```
* 导出历史列表中的所有Movies（电影）为export_movies_history.csv：
```
export_trakt.py -c config.ini -t movies -o export_movies_history.csv -l history
```
* 将导出后的文件放到本项目文件夹下并修改config.ini配置文件，已经标注了必填项和建议填写项
* 启动``Trakt-to-Bangumi.py``开始转换，然后耐心等待（内容为实时写入如有不便可退出）
* 转换完后如果未修改过输出文件名直接启动``BangumiMigrate-Csv-Pro.py``即可开始导入至Bangumi，如有修改输出名请修改配置文件中对应导入项

#### 本项目生成文件说明
本项目总共会生成文件``3``个
* `bangumi_export.csv`：转换后的文件
* `failure_log_20250×0×_××××××.csv`：条目匹配失败日志
* `success_log_20250×0×_××××××.csv`：条目匹配成功日志

<ins>_另外需要注意本项目尚未做归档文件功能，旧同名生成文件会覆盖新生成文件，请注意自行备份迁移_</ins>


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
