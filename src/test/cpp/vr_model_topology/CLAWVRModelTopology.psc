Scriptname CLAWVRModelTopology

; Queue one current wolf model graph snapshot. Positive, increasing nonce.
String Function Capture(Int nonce) Global Native

; Read status and snapshot for the same nonce. Does not queue a task.
String Function Read(Int nonce) Global Native
