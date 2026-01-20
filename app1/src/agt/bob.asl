// Agent bob in project app1

/* Initial beliefs and rules */

/* Initial goals */

!start.

/* Plans */

+!start : true <- 
    updateFeed.

+sentiment(I,V) : true <-
    //.print(I, V);
    ?message(I, A, C, O, T);
    //.print(C);
    repost(I);
    comment(I, ["music"], [raise_awareness(true), emotion("happy")]);
    react(I, "love").

//+message(I, A, C, O, T) : true <- 
//    .print(C).

+interpretation(I, sentiment(A)) : true <-
    //.print(A);
    ?message(I,AM,C,O,T);
    .print(C).
