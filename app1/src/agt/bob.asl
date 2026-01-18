// Agent bob in project app1

/* Initial beliefs and rules */
follows(bob, carol, 5.0).
follows(bob, alice, 4.0).

/* Initial goals */

!start.

/* Plans */

+!start : true <- 
    .print("hello world."); 
    // updateFeed;
    //searchContent(climate_change)
    //searchContent(no_hay)
    //searchAuthor(alice)
    updateFeed;
    ?message(I, A, C, O, T);
    repost(I);
    comment(I, ["music"], [raise_awareness(true), emotion("happy")]);
    react(I, "love").

//+message(I, A, C, O, T): true <-
//    .print(I, A, C, O, T).

//+reaction(I, A, R): true <-
//    .print(I, A, R).