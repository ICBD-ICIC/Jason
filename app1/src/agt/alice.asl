// Agent alice in project app1

/* Initial beliefs and rules */
follows(alice, bob, 8.5).

/* Initial goals */

!start.

/* Plans */

+!start : true <- 
    .print("hello world."); 
    createPost(["floods"], [raise_awareness(true), emotion("worry")]).
