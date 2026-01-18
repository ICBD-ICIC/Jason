// Agent carol in project app1

/* Initial beliefs and rules */
//Static beliefs in .asl are not affected by removePercept().
//follows(carol, alice, 7.3).
//follows(carol, bob, 5.0).

/* Initial goals */

!start.

/* Plans */

+!start : true <- 
    .print("hello world.");
    //createLink(alice);
    //createLink(bob);
    removeLink(alice).

/* +follows(A,B,C) : true <-
    .print(A,B,C). */

-follows(A,B,C) : true <-
    .print(A,B,C).