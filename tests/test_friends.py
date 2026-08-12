"""Tests du système d'amis."""

from src.database import db
from src.friends import (
    accept_friend_request,
    decline_friend_request,
    get_friends_list,
    send_friend_request,
)
from src.models import Friendship, User


def create_test_user(username: str) -> User:
    """Crée un utilisateur de test en base."""
    user = User(username=username, email=f"{username.lower()}@filmatrix.fr")
    user.set_password("Azerty1!")
    db.session.add(user)
    db.session.commit()
    return user


def test_send_friend_request_creates_pending_friendship(app):
    """Sending a friend request should create a pending friendship."""
    with app.app_context():
        alice = create_test_user("Alice")
        bob = create_test_user("Bob")

        success = send_friend_request(alice, bob)
        db.session.commit()

        assert success is True
        friendship = Friendship.query.first()
        assert friendship.status == "pending"
        assert friendship.requester_id == alice.id
        assert friendship.receiver_id == bob.id


def test_send_friend_request_fails_to_self(app):
    """A user should not be able to send a friend request to themselves."""
    with app.app_context():
        alice = create_test_user("Alice")

        success = send_friend_request(alice, alice)

        assert success is False


def test_send_friend_request_fails_if_already_exists(app):
    """A second friend request between the same two users should fail."""
    with app.app_context():
        alice = create_test_user("Alice")
        bob = create_test_user("Bob")

        send_friend_request(alice, bob)
        db.session.commit()

        second_attempt = send_friend_request(bob, alice)

        assert second_attempt is False


def test_accept_friend_request_by_receiver_succeeds(app):
    """The receiver should be able to accept a pending friend request."""
    with app.app_context():
        alice = create_test_user("Alice")
        bob = create_test_user("Bob")

        send_friend_request(alice, bob)
        db.session.commit()
        friendship = Friendship.query.first()

        success = accept_friend_request(friendship.id, bob.id)
        db.session.commit()

        assert success is True
        assert friendship.status == "accepted"


def test_accept_friend_request_by_requester_fails(app):
    """The requester should not be able to accept their own request."""
    with app.app_context():
        alice = create_test_user("Alice")
        bob = create_test_user("Bob")

        send_friend_request(alice, bob)
        db.session.commit()
        friendship = Friendship.query.first()

        success = accept_friend_request(friendship.id, alice.id)

        assert success is False
        assert friendship.status == "pending"


def test_get_friends_list_returns_accepted_friends_both_ways(app):
    """get_friends_list should return friends regardless of who sent the request."""
    with app.app_context():
        alice = create_test_user("Alice")
        bob = create_test_user("Bob")
        carol = create_test_user("Carol")

        send_friend_request(alice, bob)
        send_friend_request(carol, alice)
        db.session.commit()

        for friendship in Friendship.query.all():
            friendship.status = "accepted"
        db.session.commit()

        alice_friends = get_friends_list(alice.id)
        friend_names = {friend.username for friend in alice_friends}

        assert friend_names == {"Bob", "Carol"}


def test_decline_friend_request_removes_it(app):
    """Declining a friend request should remove it from the database."""
    with app.app_context():
        alice = create_test_user("Alice")
        bob = create_test_user("Bob")

        send_friend_request(alice, bob)
        db.session.commit()
        friendship = Friendship.query.first()

        success = decline_friend_request(friendship.id, bob.id)
        db.session.commit()

        assert success is True
        assert Friendship.query.count() == 0