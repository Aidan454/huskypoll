import './LoginCard.css'
import { Link } from 'react-router'

export default function Login(){
    return (
    <>
    <div id='login'>
        <h1>HuskyPoll</h1>
        <div className='buttons'>
            <a class='btn'>Login with email(@uconn.edu)</a>
            <a class='btn'>Login with NetID (SSO)</a>
            <Link to="/Home">Bypass Login</Link>
        </div>
    </div>
    </>)
}