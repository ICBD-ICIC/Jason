{ include("common.asl") }

/* Initial beliefs and rules */
political_standpoint(ps_placeholder).
demographics(d_placeholder).
persona_description(pd_placeholder).

/* Initial goals */
!initiate_affectivity.

/* Plans */
+love(republicans, LR) : 
    not finish &
    LR >= 5
<-
    .stopMAS.

+love(democrats, LD) : 
    not finish &
    LD >= 5
<-
    .stopMAS.