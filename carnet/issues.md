# Issues in the log files
Collected logs contain the following issues. Some of them may not be technically relevant, however, investigation should statrt from A-Series issues, as they will persist in both F-Series and H-Series. 

## A-Series

### Clean start not running
Using --clean-start option causes the scenario execution to fail within wait for publishers... 

### Missing messages 
> Didn't receive a multicast SD message for 2200ms.

maybe just a shutdown issue? Ignore for now...

### Host endpoint (routing manager) not up
> local_client_endpoint::connect: Couldn't connect to: /home/vm-user/workspace/mininet-vsomeip-evaluation/vsomeip-inf-0 (No such file or directory / 2)

Try to extend delay after manager startup, before starting other applications. Could also indicate that the manager is not starting up properly. 

### Sending issues
> cei::send_cbk received error: Broken pipe (32) /home/vm-user/workspace/mininet-vsomeip-evaluation/vsomeip-inf-0 1 9 (0000): [0000.0000.0000]

Happens during shutdown. Ignore for now.

> connect_cbk: resume sending to: /home/vm-user/workspace/mininet-vsomeip-evaluation/vsomeip-zcrl-0

Happens during startup. Inverstigate together with routing manager startup issues.

### Derigistering application timeout
> 1389 couldn't deregister application - timeout
followed by
> local_uds_client_endpoint_impl::receive_cbk Error: Operation canceled
> 2026-03-02 16:58:37.761400 [info] Exiting vsomeip application...

Could indicate that an application is not responding, e.g., hanging in message processing 

--> happens only when remote connection shutsdown before local application. Ignore for now.

### Remote subscribe already pending
> on_remote_subscribe a remote subscription is already pending [1799.0001.dae9] from 10.0.0.13:20119

maybe ```check_acknowledgements_complete_and_subscribe``` triggers a second subscription for multipart subscribe messages
is actually not that big of a deal to send another subscribe ack?

## F-Series

### Sinature not verified
> validate_subscribe_ack_and_verify_signature SIGNATURE NOT VERIFIED for service: 4001 instance: 1

May be the same as the nonce issue below. Add more detailed logging first.

## H-Series

### Missing statistic recording messages
No ```statistics_recorder``` messages in the logs

### Nonces not matching for service
> has_subscriber_challenge_nonce_and_remove Nonces not matching for service

Check where the old nonce is coming from. Maybe during subscriber validation a second subscription is issued with a new nonce --> can we update the subscriber challenge nonce at the publisher side?
Should we cache nonces for a certain time? Maybe 5 offer cycles? Or cache the 5 latest nonces?

maybe multiple TLSA resolutions? 
    - not because of tlsa_reply_ptr = tlsa_reply_ptr->tlsa_reply_next_;

which caches are responible?
    std::shared_ptr<challenge_nonce_cache> challenge_nonce_cache_; <-- do this one first as it has the most direct connection to the issue
    std::shared_ptr<eventgroup_subscription_cache> eventgroup_subscription_cache_;
    std::shared_ptr<eventgroup_subscription_ack_cache> eventgroup_subscription_ack_cache_;

> [warning] validate_subscribe_ack_and_verify_signature SIGNATURE NOT VERIFIED for service: 5002 instance: 1

This should be fixed now!

### Anything special with these services?
6075
7013
6054


### Should we do something about premature offers:

process_offerservice_serviceentry: Offer for required but not yet requested service


### Something gets stuck with DNSSEC replies when processing 

TLSA 52 

SVCB 64