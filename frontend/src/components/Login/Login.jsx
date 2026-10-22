import './Login.css'

export default function Login(){
    return (
    <>
    <div id='login'>
        <h1>HuskyPoll</h1>
        <div className='buttons'>
            <a class='btn'>Login with email(@uconn.edu)</a>
            <a class='btn'>Login with NetID (SSO)</a>
        </div>
    </div>
    </>)
}