# Manual Check for Story Clustering

After getting the similarity results, I manually checked the article pairs to see if they were actually talking about the same story.

At first I tried a threshold of 0.85. The results were not bad, but I noticed that some articles got a high similarity score just because they had similar words or were about the same general topic.

For example, two articles about different iPhones were matched together, even though they were not the same news story.

I tested the results again and changed the threshold to 0.865. This gave me better groups and removed most of the wrong matches.

## Groups that looked correct

### Cluster 1
Articles: 1, 80

Both articles are about the escalation and ground fighting in Yemen.

### Cluster 2
Articles: 58, 84, 94

These articles are about Trump's statements that the Iran war could end after the midterm elections.

### Cluster 3
Articles: 59, 74

Both articles discuss the Palestinian elections and disagreements about the election process.

### Cluster 4
Articles: 96, 103

Both articles are related to Merz and the political situation after the AfD election result.

### Cluster 5
Articles: 108, 129

Both articles discuss water problems and drought in Germany.

## Some wrong matches I found

### Articles 73 and 79
Similarity: 0.860

Both are about Apple and iPhones, but they are different stories. One is about a foldable iPhone and the other is about the iPhone 18 Pro camera.

### Articles 43 and 84
Similarity: 0.860

Both mention Trump and the midterm elections, but they are not the same story. One is about mail voting and the other is about the Iran war.

### Articles 120 and 129
Similarity: 0.858

Both are about drought and water problems, but one is about France and the other is about Germany.

## What I learned

The similarity score is useful, but a high score does not always mean that two articles are about the same event. Sometimes the model matches articles because they have similar topics, people, or words.

After checking the results manually, I decided to use 0.865 as the threshold for this version of the project.