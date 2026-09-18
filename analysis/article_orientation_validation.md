# Article-Level Orientation Validation

## Method

For the article-level analysis, I selected 20 Arabic articles from Al Jazeera and DW Arabic.

I used the headline and article text as input for the LLM. I asked the model to look only at the article content and not use the source name when deciding the orientation.

For each article, I saved the political alignment, ideological tendency, confidence, and a short reason.

If the article did not have enough information to show a clear orientation, I used `unclear` instead of trying to force a label.

I saved these results in a separate table called `article_orientation`.

## Results

I tested the method on 20 articles.

Most of the results were `unclear`. The main reason was that many of the articles were normal news reports. They talked about political events and different political sides, but this did not always mean that the article itself had a clear political orientation.

I think this is important because an article talking about a right-wing or left-wing party does not automatically make the article right-wing or left-wing.

## Good Examples

Article 43 was about the legal dispute over mail voting in the United States. It included political positions and the court decision, but I did not find enough evidence to give the article a specific orientation, so the result was `unclear`.

Article 54 was about the disagreement between Turkey and Greece. The article included information and positions from both sides, so I also kept it as `unclear`.

Article 59 included different Palestinian opinions about the electoral process. Because there were different views in the same article, I did not think there was enough evidence to give the article one specific orientation.

I considered these good results because the model did not give an ideological label just because the topic was political.

## Unclear Examples

Article 58 had very little text in the collected article body. Because of this, there was not enough information to make a good classification, so I used `unclear` with low confidence.

Article 75 was also a short news report about political parties and electoral lists. There was not enough information in the text to identify a clear orientation.

These examples showed me why having an `unclear` option is useful.

## Difficult Examples

Some articles were more difficult than others.

Articles 87, 96, 100, and 103 talked about AfD in Germany. These articles can be difficult for automatic analysis because the model could classify the article based on the political party mentioned in it instead of looking at the orientation of the article itself.

Article 10 was also difficult because it included criticism of Reform UK and information from different newspapers. I did not think that criticism of one political party was enough to decide the orientation of the whole article.

For these examples, I kept the result as `unclear`.

I did not find a clearly wrong forced label in these 20 articles, but these were the examples where I think an automatic model could easily make a wrong classification.

## Source-Level and Article-Level Comparison

After that, I compared the article-level results with the source profiles.

For Al Jazeera, I had already marked the political alignment and ideological tendency as `unclear`. Most of the selected Al Jazeera articles were also `unclear` in the article-level analysis.

For DW Arabic, the source profile had `independent` for political alignment and `unclear` for ideological tendency. Most of the tested DW articles were `unclear` at article level.

I noticed that the source-level and article-level results are not always directly comparable. For example, `independent` describes the source in general, while `unclear` at article level means that I could not find enough evidence in that specific article to give it an ideological label.

Because of this, I do not automatically give an article the same orientation as its source.

## Limitations

This was only a small test using 20 articles from two news sources, so I see it as an initial experiment.

I also found that political orientation can be difficult to put into simple labels, especially when the articles are about different countries and political systems.

The article-level results are LLM estimates, so they should not be treated as objective facts.

Also, ideological orientation does not mean that a news source or article is true, false, good, bad, or reliable. This analysis is only about orientation.