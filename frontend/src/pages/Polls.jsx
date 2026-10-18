import Header from "../components/Header/Header";
import PollCard from "../components/PollCard/PollCard";

export default function Polls() {
    return (
        <>
            <Header />
            <h1>Polls</h1>
            <PollCard question="1 or 2?" type="Multiple Choice"/>
            <PollCard question="Type something" type="Text"/>
            <PollCard question="Favorite number?" type="Numeric"/>
        </>
    )
}
