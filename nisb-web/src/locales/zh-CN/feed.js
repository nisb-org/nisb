export default {
  toolbar: {
    tab: 'Feed',
    tabTitle: '广场（Feed）',
    expandLeftSidebar: '展开左侧栏',
    expandRightSidebar: '展开右侧栏'
  },

  panel: {
    tabs: {
      mine: {
        full: '📝 我的 Feed',
        noEmoji: '我的 Feed',
        compact: '我的'
      },
      latest: {
        full: '🌐 广场',
        noEmoji: '广场',
        compact: '广场'
      },
      tags: {
        full: '🏷️ 标签',
        noEmoji: '标签',
        compact: '标签'
      },
      foryou: {
        full: '✨ For You',
        noEmoji: 'For You',
        compact: '推荐'
      }
    },

    tag: {
      clear: '清除标签'
    },

    actions: {
      notifications: '通知',
      me: '我的',
      refresh: '刷新',
      loading: '加载中…',
      menu: '菜单'
    },

    drawer: {
      close: '关闭'
    },

    delete: {
      title: '确定删除？',
      desc: '此操作不可撤销，但已被他人缓存的副本无法清除。',
      cancel: '取消',
      confirm: '删除'
    },

    toast: {
      refreshFailed: '刷新失败。',
      deleteFailed: '删除失败。',
      deleted: '已删除。'
    }
  },

  detail: {
    common: {
      busy: '...'
    },

    actions: {
      close: '关闭'
    },

    author: {
      avatarAlt: '头像'
    },

    follow: {
      follow: '关注',
      unfollow: '取消关注',
      compactFollow: '关',
      compactUnfollow: '取关'
    },

    bookmark: {
      bookmark: '收藏',
      unbookmark: '取消收藏',
      compactBookmark: '藏',
      compactUnbookmark: '取消'
    },

    status: {
      deleted: '撤回'
    },

    states: {
      loading: '加载中…'
    },

    fallbacks: {
      untitled: '未命名',
      unknownAuthor: '未知用户'
    },

    errors: {
      toolFailed: '工具调用失败。',
      allToolCandidatesFailed: '所有工具候选均失败。',
      missingFeedId: '缺少 feed_id。'
    },

    toast: {
      followFailed: '关注失败。',
      bookmarkFailed: '收藏失败。'
    }
  },

  comments: {
    title: '评论',

    actions: {
      refresh: '刷新',
      loading: '加载中…',
      post: '发布',
      posting: '发布中…'
    },

    editor: {
      placeholder: 'Markdown'
    },

    states: {
      loading: '加载中…',
      empty: '暂无评论。'
    },

    errors: {
      toolFailed: '工具调用失败。',
      allToolCandidatesFailed: '所有工具候选均失败。'
    },

    toast: {
      loadFailed: '加载评论失败。',
      postFailed: '发布评论失败。',
      replyEmpty: '回复内容为空。',
      replyFailed: '回复失败。',
      deleteFailed: '删除评论失败。'
    }
  },

  commentNode: {
    author: {
      avatarAlt: '头像'
    },

    fallbacks: {
      unknownAuthor: '未知用户'
    },

    vote: {
      like: '赞',
      downvote: '踩',
      spam: '垃圾'
    },

    actions: {
      reply: '回复',
      delete: '删除',
      post: '发布',
      posting: '发布中…',
      cancel: '取消'
    },

    editor: {
      replyPlaceholder: '回复（Markdown）'
    },

    status: {
      pending: '待发送',
      failed: '发送失败',
      deleted: '已删除'
    },

    toast: {
      voteFailed: '投票失败。'
    }
  },

  tagsView: {
    title: '热门标签',

    actions: {
      refresh: '刷新',
      loading: '加载中…'
    },

    states: {
      empty: '暂无标签。'
    },

    toast: {
      loadFailed: '获取标签失败。'
    }
  },

  timeline: {
    actions: {
      loadMore: '加载更多',
      loading: '加载中…'
    },

    states: {
      empty: '暂无帖子。'
    },

    errors: {
      listFailed: 'Feed 列表加载失败。'
    },

    toast: {
      refreshFailed: '刷新失败。',
      loadMoreFailed: '加载更多失败。'
    }
  },

  itemCard: {
    author: {
      avatarAlt: '头像'
    },

    fallbacks: {
      untitled: '未命名',
      unknownAuthor: '未知用户',
      unknownSource: '未知来源'
    },

    vote: {
      like: '点赞',
      boost: '助推',
      downvote: '点踩（24h）',
      spam: '标记垃圾（7d）'
    },

    bookmark: {
      bookmark: '收藏',
      unbookmark: '取消收藏'
    },

    actions: {
      delete: '删除'
    },

    score: {
      title: '热度：{score}',
      inline: '· 热度：{score}'
    },

    toast: {
      voted: '已投票。',
      voteFailed: '投票失败。',
      bookmarked: '已收藏。',
      unbookmarked: '已取消收藏。',
      bookmarkFailed: '收藏失败。'
    },

    state: {
      unread: '未读',
      read: '已读'
    },

    signals: {
      comments: '{count} 条评论',
      notifications: '{count} 条通知'
    }
  },

  notifications: {
    title: '通知',

    actor: {
      avatarAlt: '头像',
      unknown: '未知用户'
    },

    actions: {
      markAllRead: '全部标记已读',
      markAllReadCompact: '✓✓',
      refresh: '刷新',
      refreshCompact: '↻',
      loading: '加载中…',
      read: '已读',
      markRead: '标记已读'
    },

    states: {
      empty: '暂无通知。'
    },

    ref: {
      feed: 'Feed: {id}'
    },

    time: {
      minute: '{count}分',
      hour: '{count}小时',
      day: '{count}天',
      week: '{count}周'
    },

    toast: {
      loadFailed: '加载通知失败。',
      markReadFailed: '标记已读失败。',
      markAllReadFailed: '全部标记已读失败。'
    }
  },

  mePanel: {
    title: '我',
    subtitle: '你的 Feed 身份、收藏条目与关注关系。',

    tabs: {
      ariaLabel: 'Feed 用户面板标签',
      profile: '资料',
      bookmarks: '收藏',
      following: '正在关注',
      followers: '关注者'
    },

    profile: {
      title: 'Feed 身份',
      desc: '这个身份会显示在 Feed 互动中。',
      hint: '头像、显示名和简介会帮助工作区里的其他用户识别你的评论、投票和收藏。'
    },

    bookmarks: {
      title: '已保存的 Feed 条目',
      desc: '打开或移除你收藏过的条目。'
    },

    following: {
      title: '正在关注',
      desc: '你正在关注这些用户的 Feed 动态。'
    },

    followers: {
      title: '关注者',
      desc: '这些用户正在关注你的 Feed 动态。'
    },

    labels: {
      userId: '用户 ID',
      avatar: '头像',
      displayName: '显示名',
      bio: '简介'
    },

    placeholders: {
      displayName: '输入显示名',
      bio: '写一点关于你自己的介绍',
      searchFollowing: '搜索正在关注',
      searchFollowers: '搜索关注者'
    },

    actions: {
      refresh: '刷新',
      loading: '加载中...',
      save: '保存',
      saving: '保存中...',
      uploadAvatar: '上传头像',
      uploading: '上传中...',
      clear: '清除',
      removeBookmark: '移除收藏',
      unfollow: '取消关注',
      followBack: '回关',
      working: '处理中...'
    },

    states: {
      noBookmarks: '还没有收藏。',
      noFollowing: '还没有关注用户。',
      noFollowers: '还没有关注者。'
    },

    avatar: {
      alt: '头像',
      inputLabel: '选择头像图片'
    },

    fallbacks: {
      unknownUser: '未知用户',
      untitled: '未命名'
    },

    toast: {
      loadProfileFailed: '加载资料失败',
      refreshFailed: '刷新失败',
      saveFailed: '保存失败',
      saved: '已保存',
      bookmarkRemoved: '已移除收藏',
      removeBookmarkFailed: '移除收藏失败',
      unfollowFailed: '取消关注失败',
      followFailed: '关注失败',
      uploadFailed: '上传头像失败'
    }
  }
}
