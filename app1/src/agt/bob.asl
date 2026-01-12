// Agent bob in project app1

/* Initial beliefs and rules */
follows(carol, 5.0).
follows(alice, 4.0).

/* Initial goals */

!start.

/* Plans */

+!start : true <- .print("hello world.").
