See integration playbook. Auth-gated testing steps for Kalun (Emergent Google Auth).

Create test user + session:
mongosh --eval "
use('test_database');
var userId = 'test-user-' + Date.now();
var sessionToken = 'test_session_' + Date.now();
db.users.insertOne({user_id:userId, email:'test.user.'+Date.now()+'@example.com', name:'Test CEO', picture:'https://via.placeholder.com/150', created_at:new Date().toISOString()});
db.user_sessions.insertOne({user_id:userId, session_token:sessionToken, expires_at:new Date(Date.now()+7*24*60*60*1000).toISOString(), created_at:new Date().toISOString()});
print('Session token: ' + sessionToken);
"

Backend: send Authorization: Bearer <session_token> OR cookie session_token.
Browser: set cookie session_token (httpOnly, secure, sameSite None), then goto app.
