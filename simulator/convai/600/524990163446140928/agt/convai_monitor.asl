/* ==========================================================
    CoNVaI Monitor Agent

    Termination conditions:
        1. Hard cap:   N/2+1 agents have reported max_cycles_reached
        2. Inactivity: N/2+1 agents have reported idle_limit_reached
                       and none have since sent still_active

    The monitor reacts to two events sent by agents:

        +-idle_limit_reached(AgentName)
            Agent's consecutive idle cycles exceeded X.
            Added to idle_done set.

        +max_cycles_reached(AgentName)
            Agent's cycle counter exceeded T.
            Added to cycle_done set. Never retracted since
            cycles only go forward.

    Termination fires when either set contains N/2+1 agents (majority).

    Parameters:
        total_agents(N) - total number of agents in the simulation
   ========================================================== */

+idle_limit_reached(Agent): total_agents(N) <-
    .findall(A, idle_limit_reached(A), Done);
    IC = .length(Done);
    Threshold = N;
    if (IC >= Threshold) {
        ia.saveLogs([info("Termination: majority idle."), idle_count(IC)]);
        .stopMAS
    } else {
        ia.saveLogs([idle_count(IC)])
    }.

+max_cycles_reached(Agent): total_agents(N) <-
    .findall(A, max_cycles_reached(A), Done);
    CC = .length(Done);
    Threshold = N;
    if (CC >= Threshold) {
        ia.saveLogs([info("Termination: majority reached max cycles."), cycle_count(CC)]);
        .stopMAS
    } else {
        ia.saveLogs([cycle_count(CC)])
    }.