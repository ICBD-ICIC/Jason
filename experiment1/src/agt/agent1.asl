/* Initial beliefs and rules */
political_standpoint(Republican).
demographics("Your demographics are male, white, hispanic or latino, with some college no degree, and you live in the U.S.").
persona_description("You are a politically engaged individual, likely conservative in your leanings. You are skeptical of climate change policies and their potential economic impacts. You are active on social media and use hashtags to express your opinions and connect with others who share your views. You are not afraid to directly criticize political figures.").

/* Initial goals */

!start.

/* Plans */

+!start : true <- 
    .print("agent1 before wait");
    .wait(1000);
    .print("agent1 after wait");
    updateFeed;
    !read_messages.

+message(I,A,C,O,T) : true <-
    ia.interpret(C, Interpretation);
    .print(Interpretation).