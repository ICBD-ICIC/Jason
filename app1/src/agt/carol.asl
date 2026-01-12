// Agent carol in project app1

/* Initial beliefs and rules */
follows(alice, 7.3).
follows(bob, 5.0).

/* Initial goals */

!start.

/* Plans */

+!start : true <- .print("hello world.").
