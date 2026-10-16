import { Link } from "react-router"
import './Navbar.css'

export default function Navbar(){
    return (
    <>
    <nav>
        <Link className="navlink" to="/InstructorHome">Home</Link>
        <Link className="navlink" to="/Polls">Polls</Link>
    </nav>
    </>)
}
