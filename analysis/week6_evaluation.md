# Week 6 — Small Evaluation

## Objective

I manually reviewed a small number of story groups to check whether the articles actually covered the same news story. I also reviewed how the portal displays ideological orientation and uncertainty.

## 1. Messi — Correct Grouping

I checked the articles about Lionel Messi and his international career with Argentina.

The articles covered the same main story, and the grouping was correct.

**Result:** Correct grouping.

## 2. Artificial Intelligence — False Positive

I reviewed a group containing articles about artificial intelligence.

Although the articles discussed AI, they did not all cover the same specific news event. The system grouped them because their topics and headlines were similar.

**Result:** False positive.

**Possible improvement:** Improve the similarity validation to distinguish articles about the same event from articles about the same general topic.

## 3. Iran News — Correct Grouping

I reviewed a sample of articles in the Iran-related story group.

The inspected articles were related to the same news story, and the grouping was appropriate.

**Result:** Correct grouping in the reviewed sample.

## 4. Houthi Escalation — Correct Grouping

I checked articles related to the Houthi escalation.

The inspected articles covered the same story, and the grouping was consistent.

**Result:** Correct grouping in the reviewed sample.

## Ideological Orientation Evaluation

The portal displays political alignment, ideological tendency, and confidence information.

It also clearly displays uncertain classifications using the label "غير واضح".

These labels are experimental estimates. This evaluation checked their presentation and usefulness in the interface, but it did not independently establish the political orientation of every article.

## Conclusion

The manual evaluation found successful story groups as well as a false-positive example.

The main limitation is that articles discussing a similar general topic can sometimes be grouped even when they do not describe the same specific event.

Overall, the comparison functionality worked for the reviewed samples, while the false-positive case shows that story clustering can still be improved.

This was a small qualitative evaluation, not a comprehensive accuracy measurement.