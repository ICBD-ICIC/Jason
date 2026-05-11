/* ==========================================================
    CoNVaI Monitor Agent

    Termination conditions:
        1. Hard cap:   N/2+1 agents have reported max_cycles_reached
        2. Inactivity: N/4+1 agents have reported idle_limit_reached
                       and none have since sent still_active

    The monitor reacts to two events sent by agents:

        +-idle_limit_reached(AgentName)
            Agent's consecutive idle cycles exceeded X.
            Added to idle_done set.

        +max_cycles_reached(AgentName)
            Agent's cycle counter exceeded T.
            Added to cycle_done set. Never retracted since
            cycles only go forward.

    Parameters:
        total_agents(N) - total number of susceptible agents in the simulation
   ========================================================== */

+idle_limit_reached(Agent): total_agents(N) <-
    .findall(A, idle_limit_reached(A), Done);
    IC = .length(Done);
    Threshold = (N / 2) + 1;
    if (IC >= Threshold) {
        ia.saveLogs([info("Termination: majority idle."), idle_count(IC)]);
        .stopMAS
    } else {
        ia.saveLogs([idle_count(IC)])
    }.

+max_cycles_reached(Agent): total_agents(N) <-
    .findall(A, max_cycles_reached(A), Done);
    CC = .length(Done);
    Threshold = (N / 4) + 1;
    if (CC >= Threshold) {
        ia.saveLogs([info("Termination: majority reached max cycles."), cycle_count(CC)]);
        .stopMAS
    } else {
        ia.saveLogs([cycle_count(CC)])
    }.