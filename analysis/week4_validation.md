# Week 4 Validation

This week I tested the complete backend pipeline with real Arabic articles from Al Jazeera and DW Arabic.

I ran the full pipeline starting from collecting the articles, preparing the text, grouping similar stories, and preparing the data for the backend.

I also tested the duplicate handling after running the collector again. The result was:

- Duplicate URLs: 0
- Duplicate content: 0

I tested several story groups manually. Clusters 2, 7, and 10 gave good results and included related articles from both Al Jazeera and DW Arabic.

I found one wrong grouping in Cluster 9. The articles were all about artificial intelligence, but they were not about the same event. Their similarity scores were slightly above the current threshold of 0.865, so they were grouped together.

I decided to keep the threshold at 0.865 for now because increasing it could also remove some correct or closely related groups. This is one limitation of using semantic similarity alone.

I also tested the backend functions and FastAPI endpoints. They correctly returned the story groups and the articles inside each group with the source, headline, date, URL, and orientation information.

The pipeline now runs all the main backend steps in one command, and simple logging was added to record whether each step completed successfully.
