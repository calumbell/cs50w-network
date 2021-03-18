from django.core.serializers import serialize
from django.core.paginator import Paginator
from django.contrib.auth import authenticate, login, logout
from django.db import IntegrityError
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
import json

from .models import User, Post, Relationship

def index(request):
    return render(request, "network/index.html")


def login_view(request):
    if request.method == "POST":

        # Attempt to sign user in
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        # Check if authentication successful
        if user is not None:
            login(request, user)
            return HttpResponseRedirect(reverse("index"))
        else:
            return render(request, "network/login.html", {
                "message": "Invalid username and/or password."
            })
    else:
        return render(request, "network/login.html")


def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse("index"))


def register(request):
    if request.method == "POST":
        username = request.POST["username"]
        email = request.POST["email"]

        # Ensure password matches confirmation
        password = request.POST["password"]
        confirmation = request.POST["confirmation"]
        if password != confirmation:
            return render(request, "network/register.html", {
                "message": "Passwords must match."
            })

        # Attempt to create new user
        try:
            user = User.objects.create_user(username, email, password)
            user.save()
        except IntegrityError:
            return render(request, "network/register.html", {
                "message": "Username already taken."
            })
        login(request, user)
        return HttpResponseRedirect(reverse("index"))
    else:
        return render(request, "network/register.html")

def modify_post(request, id):
    post = Post.objects.get(id=id)
    
    if request.user != post.author:
        return HttpResponse('You do not have permission to edit this post', status=403)

    data = json.loads(request.body)
    post.message = data['message']
    post.save()
    
    return HttpResponse({'message' : data['message']})
    

def follow(request, username):
    user = User.objects.get(username=username)

    follow_object = user.relationships_to.filter(from_user=request.user, status=1)

    if follow_object:
        follow_object.delete()
        is_followed = False
    else:
        follow_object = Relationship(from_user=request.user, to_user=user, status=1)
        follow_object.save()
        is_followed = True

    response = {
        'username' : user.username,
        'post-count' : user.posts.count(),
        'following' : user.relationships_from.count(),
        'followed-by' : user.relationships_to.count(),
        'is_followed' : is_followed,
    }

    return HttpResponse(json.dumps(response), content_type='application/json')
    

def get_user_profile(request, username):
    user = User.objects.get(username=username)
    
    if user.relationships_to.filter(from_user=request.user, status=1):
        is_followed = True
    else:
        is_followed = False

    response = {
        'username' : user.username,
        'post-count' : user.posts.count(),
        'following' : user.relationships_from.count(),
        'followed-by' : user.relationships_to.count(),
        'is_followed' : is_followed,
    }

    return HttpResponse(json.dumps(response), content_type='application/json')

def get_posts(request):
    pageNumber = int(request.GET.get("page"))
    postsPerPage = int(request.GET.get("perPage"))
    user = request.GET.get("user") or None
    feed = request.GET.get("feed") or None

    # if feed flag is raised, get posts of users request.user is following
    if feed:
        follow_relationships = request.user.relationships_from.filter(status=1) # Relationships 
        following = User.objects.filter(id__in=follow_relationships.values('to_user')) # Users
        posts = Post.objects.filter(author__in=following) # Posts       

    # if user flag is raised, get posts by a specific user
    elif user:
        user_obj = User.objects.get(username=user)
        posts = Post.objects.filter(author=user_obj)  

    # else get all posts
    else:
        posts = Post.objects.all()
    

    # handle pagination and serialize posts
    paginator = Paginator(posts, postsPerPage)
    page = paginator.get_page(pageNumber)

    serializer = serialize("json", page, use_natural_foreign_keys=True)

    response = {
        "requested_by" : request.user.username,
        "posts" : serializer,
        "page" : pageNumber,
        "page_count" : paginator.num_pages,
        "has_next_page" : page.has_next(),
        "has_previous_page" : page.has_previous(),
    }

    return HttpResponse(json.dumps(response), content_type='application/json')

def like_post(request, id):
    post = Post.objects.get(id=id)
    state = json.loads(request.body)['state']
    if state == 'Like':
        post.liked_by.add(request.user)
        state = 'Unlike'
    elif state == 'Unlike':
        post.liked_by.remove(request.user)
        state = 'Like'
    post.save()
    
    return HttpResponse(json.dumps({'state': state}), content_type='application/json')

def submit_post(request):
    if request.method != "POST":
        return render(request, "index.html")  

    # Add new post to DB
    data = json.loads(request.body)
    post = Post(author=request.user, message=data['message'])
    post.save()

    # Respond with the new post in JSON
    response = serialize("json", [post], ensure_ascii=False, use_natural_foreign_keys=True)
    return HttpResponse(response[1:-1], content_type='application/json')