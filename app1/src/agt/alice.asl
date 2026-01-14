// Agent alice in project app1

/* Initial beliefs and rules */
follows(bob, 8.5).

/* Initial goals */

!start.

/* Plans */

+!start : true <- 
    .print("hello world."); 
    ?follows(X, Y); 
    .print(X, Y); 
    createPost(["floods"], [raise_awareness(true), emotion("worry")]).
