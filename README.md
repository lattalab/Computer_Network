# 2024 NSYSU  Computer Network Programming Assignment
- [x] Finish the basic requirement - 2024/6/14
- [ ] Optimize the code list
* change to use UDP to simulate the TCP mechanism
* You have to followint schema:
  * The TCP segment structure.
  * The initial sequence number should be set randomly (1~10000).
  * The program should work fine under a subnetwork.
* In step1 , MSS means the maximize data size that a TCP packet can transmit (Not included TCP header size)
* In step2 , can use fork to simulate activate 2 client at the same time
* In step4 , apply Go-Back-N for fixed sender window size.
  *  Delayed ACK will not affect step 5, 6, 7, 8
* 將理論的finite state實現出來，最初版本為了趕時間而亂做 - `step 5, 6, 7, 8`
* Study on thread server
